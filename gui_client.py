import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from tkinter.scrolledtext import ScrolledText
import queue

# --- (Copied from previous step, with one key change) ---
class ChatClient:
    def __init__(self, gui_queue):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_thread = None
        self.connected = False
        self.client_reader = None
        # This queue is used to pass messages from the listener thread to the GUI thread
        self.gui_queue = gui_queue

    def connect(self, host, port):
        try:
            self.client_socket.connect((host, port))
            self.connected = True
            self.client_reader = self.client_socket.makefile('r', encoding='utf-8')
            self.listener_thread = threading.Thread(target=self.receive_messages)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            return True
        except Exception as e:
            self.gui_queue.put({"command": "ERROR", "payload": f"Connection failed: {e}"})
            return False

    def send_message(self, data):
        if self.connected:
            try:
                message_json = json.dumps(data) + '\n'
                self.client_socket.sendall(message_json.encode('utf-8'))
            except Exception as e:
                self.gui_queue.put({"command": "ERROR", "payload": f"Send Error: {e}"})
                self.connected = False
        else:
            self.gui_queue.put({"command": "ERROR", "payload": "Not connected."})

    def receive_messages(self):
        """ This runs in a separate thread """
        while self.connected:
            try:
                line = self.client_reader.readline()
                if not line:
                    break  # Connection lost
                
                message = json.loads(line)
                # This is the KEY: Put the server message into the queue
                # for the GUI thread to process safely
                self.gui_queue.put(message)

            except json.JSONDecodeError:
                self.gui_queue.put({"command": "ERROR", "payload": "Received invalid JSON."})
            except Exception as e:
                if self.connected:
                     self.gui_queue.put({"command": "ERROR", "payload": f"Receive Error: {e}"})
                break
        
        self.connected = False
        self.gui_queue.put({"command": "ERROR", "payload": "Disconnected from server."})
        self.client_socket.close()

    # --- Public API for the GUI to call ---
    def login(self, username):
        self.send_message({"command": "LOGIN", "payload": username})

    def send_private_message(self, recipient, message):
        self.send_message({"command": "MSG_PRIVATE", "payload": {"recipient": recipient, "message": message}})

    def create_group(self, group_name):
        self.send_message({"command": "CREATE_GROUP", "payload": group_name})

    def join_group(self, group_name):
        self.send_message({"command": "JOIN_GROUP", "payload": group_name})

    def send_group_message(self, group_name, message):
        self.send_message({"command": "MSG_GROUP", "payload": {"group": group_name, "message": message}})

# --- (This is the new GUI class) ---

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Client")
        self.root.geometry("800x600")
        
        self.username = ""
        self.gui_queue = queue.Queue()
        self.client = ChatClient(self.gui_queue)
        
        # This dict will hold the chat room widgets: {"room_name": ScrolledText_widget}
        self.chat_windows = {}
        # This dict will hold group member lists
        self.groups_data = {}

        # --- Create GUI Widgets ---
        self.main_paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True)

        # Left Frame (Users and Groups)
        self.left_frame = ttk.Frame(self.main_paned_window, width=200)
        self.main_paned_window.add(self.left_frame, weight=1)

        # User List (R4)
        ttk.Label(self.left_frame, text="Online Users").pack(pady=5)
        self.user_list_frame = ttk.Frame(self.left_frame)
        user_scrollbar = ttk.Scrollbar(self.user_list_frame, orient=tk.VERTICAL)
        self.user_list = tk.Listbox(self.user_list_frame, yscrollcommand=user_scrollbar.set, exportselection=False)
        user_scrollbar.config(command=self.user_list.yview)
        user_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.user_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.user_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # Add binding to open private chat
        self.user_list.bind('<Double-Button-1>', self.on_user_double_click)

        # Group List (R9)
        ttk.Label(self.left_frame, text="Chat Groups").pack(pady=5)
        self.group_list_frame = ttk.Frame(self.left_frame)
        group_scrollbar = ttk.Scrollbar(self.group_list_frame, orient=tk.VERTICAL)
        self.group_list = tk.Listbox(self.group_list_frame, yscrollcommand=group_scrollbar.set, exportselection=False)
        group_scrollbar.config(command=self.group_list.yview)
        group_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.group_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.group_list.bind('<Double-Button-1>', self.on_group_double_click)

        # Group Buttons (R8, R10)
        self.group_button_frame = ttk.Frame(self.left_frame)
        self.create_group_button = ttk.Button(self.group_button_frame, text="Create Group", command=self.create_group)
        self.create_group_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.join_group_button = ttk.Button(self.group_button_frame, text="Join Group", command=self.join_group)
        self.join_group_button.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.group_button_frame.pack(fill=tk.X, padx=5, pady=5)

        # Right Frame (Chat Rooms)
        # R5: Each chat has its own chat room (using a Notebook)
        self.chat_notebook = ttk.Notebook(self.main_paned_window)
        self.main_paned_window.add(self.chat_notebook, weight=4)

        # --- Start Application ---
        self.root.withdraw()  # Hide main window until login
        self.ask_for_connection()
        
    def ask_for_connection(self):
        # Simple dialog for connection
        server_ip = simpledialog.askstring("Connect", "Enter Server IP:", initialvalue="127.0.0.1")
        if not server_ip:
            self.root.destroy()
            return
            
        if self.client.connect(server_ip, 12345):
            self.ask_for_username()
        else:
            messagebox.showerror("Error", "Could not connect to server.")
            self.root.destroy()

    def ask_for_username(self):
        username = simpledialog.askstring("Login", "Enter your username:")
        if username:
            self.username = username
            self.client.login(username)
            self.root.deiconify() # Show the main window
            self.root.title(f"Chat Client - {self.username}")
            # Start polling the queue
            self.poll_queue()
        else:
            self.root.destroy()
            
    def poll_queue(self):
        """
        This is the KEY function.
        It checks the queue for messages from the listener thread
        and processes them safely in the GUI thread.
        """
        try:
            while True:
                message = self.gui_queue.get_nowait()
                self.handle_server_message(message)
        except queue.Empty:
            # If queue is empty, schedule this function to run again
            self.root.after(100, self.poll_queue)

    def handle_server_message(self, message):
        """ Processes messages from the server """
        command = message.get('command')
        payload = message.get('payload')
        
        if command == "UPDATE_USER_LIST":
            self.update_user_list(payload)
        elif command == "UPDATE_GROUP_LIST":
            self.update_group_list(payload)
        elif command == "RECV_PRIVATE":
            self.handle_incoming_private(payload)
        elif command == "RECV_GROUP":
            self.handle_incoming_group(payload)
        elif command == "ERROR":
            messagebox.showerror("Server Error", payload)
            if "Username taken" in payload or "Connection failed" in payload:
                self.root.destroy()
                
    def update_user_list(self, users):
        self.user_list.delete(0, tk.END)
        for user in sorted(users):
            if user == self.username:
                self.user_list.insert(tk.END, f"{user} (You)")
            else:
                self.user_list.insert(tk.END, user)
                
    def update_group_list(self, groups):
        self.group_list.delete(0, tk.END)
        self.groups_data = groups
        for group_name, members in sorted(groups.items()):
            self.group_list.insert(tk.END, f"{group_name} ({len(members)})")

    # --- Chat Room Management (R5, R6, R7, R11) ---

    def on_user_double_click(self, event):
        """ Opens a private chat """
        try:
            selected_index = self.user_list.curselection()[0]
            user_entry = self.user_list.get(selected_index)
            username = user_entry.split(" ")[0]
            
            if username == self.username:
                return # Don't open chat with self
            
            self.open_chat_room(username, is_group=False)
        except IndexError:
            pass # No item selected
            
    def on_group_double_click(self, event):
        """ Opens a group chat """
        try:
            selected_index = self.group_list.curselection()[0]
            group_entry = self.group_list.get(selected_index)
            group_name = group_entry.split(" ")[0]
            
            if self.username not in self.groups_data.get(group_name, []):
                # R10: If not a member, ask to join
                if messagebox.askyesno("Join Group", f"You are not a member of '{group_name}'.\nDo you want to join?"):
                    self.client.join_group(group_name)
                return
            
            # Is a member, open chat
            self.open_chat_room(group_name, is_group=True)
        except IndexError:
            pass # No item selected

    def open_chat_room(self, room_name, is_group):
        """ R5: Creates or selects a chat room tab """
        if room_name in self.chat_windows:
            # Tab already exists, just select it
            for i, tab in enumerate(self.chat_notebook.tabs()):
                if self.chat_notebook.tab(i, "text") == room_name:
                    self.chat_notebook.select(i)
                    return
        
        # --- R6: Create new chat room (Frame, Window, Box) ---
        chat_frame = ttk.Frame(self.chat_notebook)
        self.chat_notebook.add(chat_frame, text=room_name)
        
        # Chat Window (displays messages)
        chat_window = ScrolledText(chat_frame, state='disabled', wrap=tk.WORD, height=10, width=50)
        chat_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_windows[room_name] = chat_window # Save reference
        
        # Chat Box Frame (for entry and send button)
        chat_box_frame = ttk.Frame(chat_frame)
        chat_box_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Chat Box (for sending messages)
        chat_box = ttk.Entry(chat_box_frame)
        chat_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Send Button
        send_button = ttk.Button(chat_box_frame, text="Send", 
                                 command=lambda: self.send_chat_message(room_name, is_group, chat_box))
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind <Return> key to send message
        chat_box.bind("<Return>", lambda event: self.send_chat_message(room_name, is_group, chat_box))
        
        # Select the newly created tab
        self.chat_notebook.select(chat_frame)

    def send_chat_message(self, room_name, is_group, chat_box_widget):
        message = chat_box_widget.get()
        if not message.strip():
            return # Don't send empty messages
            
        if is_group:
            # R11: Send Group Message
            self.client.send_group_message(room_name, message)
            # Group messages are echoed by the server, so we wait
        else:
            # R7: Send Private Message
            self.client.send_private_message(room_name, message)
            # Display our *own* message immediately
            self.display_message_in_window(room_name, f"You: {message}\n")
            
        chat_box_widget.delete(0, tk.END)

    def handle_incoming_private(self, payload):
        """ R7: Handles receiving a private message """
        sender = payload.get('sender')
        message = payload.get('message')
        
        # Open/select the chat room for the sender
        self.open_chat_room(sender, is_group=False)
        # Display the message
        self.display_message_in_window(sender, f"{sender}: {message}\n")

    def handle_incoming_group(self, payload):
        """ R11: Handles receiving a group message """
        sender = payload.get('sender')
        group_name = payload.get('group')
        message = payload.get('message')
        
        # Open/select the chat room for the group
        self.open_chat_room(group_name, is_group=True)
        # Display the message
        self.display_message_in_window(group_name, f"[{sender}]: {message}\n")

    def display_message_in_window(self, room_name, formatted_message):
        """ Helper to safely insert text into a chat window """
        if room_name in self.chat_windows:
            widget = self.chat_windows[room_name]
            widget.config(state='normal') # Enable to insert
            widget.insert(tk.END, formatted_message)
            widget.see(tk.END) # Auto-scroll
            widget.config(state='disabled') # Disable again

    # --- Group Button Functions ---
    def create_group(self):
        """ R8: Create Group """
        group_name = simpledialog.askstring("Create Group", "Enter new group name:")
        if group_name:
            self.client.create_group(group_name)
            
    def join_group(self):
        """ R10: Join Group (from selected) """
        try:
            selected_index = self.group_list.curselection()[0]
            group_entry = self.group_list.get(selected_index)
            group_name = group_entry.split(" ")[0]
            
            if self.username in self.groups_data.get(group_name, []):
                messagebox.showinfo("Info", f"You are already a member of '{group_name}'.")
                return

            self.client.join_group(group_name)
            messagebox.showinfo("Joined", f"You have joined '{group_name}'.")
        except IndexError:
            messagebox.showerror("Error", "Please select a group from the list to join.")


# --- Run the Application ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()