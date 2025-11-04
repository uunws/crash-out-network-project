import socket
import threading
import json
import time

class ChatClient:
    def __init__(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_thread = None
        self.connected = False
        # These would be connected to your GUI:
        self.gui_update_callback = None 

    def connect(self, host, port):
        try:
            self.client_socket.connect((host, port))
            self.connected = True
            
            # Use makefile for easy line-by-line reading in the listener
            self.client_reader = self.client_socket.makefile('r', encoding='utf-8')

            self.listener_thread = threading.Thread(target=self.receive_messages)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            print("Connected to server.")
        except Exception as e:
            print(f"[CONNECT ERROR] {e}")
            self.connected = False

    def send_message(self, data):
        """ Internal helper to send JSON data to server """
        if self.connected:
            try:
                message_json = json.dumps(data) + '\n'
                self.client_socket.sendall(message_json.encode('utf-8'))
            except Exception as e:
                print(f"[SEND ERROR] {e}")
                self.connected = False
        else:
            print("Not connected.")

    def receive_messages(self):
        """
        This runs in a separate thread, listening for messages from the server.
        """
        while self.connected:
            try:
                line = self.client_reader.readline()
                if not line:
                    print("Connection lost.")
                    self.connected = False
                    break
                
                message = json.loads(line)
                print(f"\n[INCOMING] {message}") # Debug print
                
                # --- This is where you update your GUI ---
                # Example:
                # if self.gui_update_callback:
                #    self.gui_update_callback(message)
                
                command = message.get('command')
                payload = message.get('payload')

                if command == "UPDATE_USER_LIST":
                    # TODO: Update your GUI's user list with the 'payload' (a list)
                    print(f"Users: {payload}")
                elif command == "UPDATE_GROUP_LIST":
                    # TODO: Update your GUI's group list with the 'payload' (a dict)
                    print(f"Groups: {payload}")
                elif command == "RECV_PRIVATE":
                    # TODO: Find the chat room for 'sender' and add the message
                    sender = payload.get('sender')
                    msg_text = payload.get('message')
                    print(f"[Private from {sender}]: {msg_text}")
                elif command == "RECV_GROUP":
                    # TODO: Find the chat room for 'group' and add the message
                    sender = payload.get('sender')
                    group = payload.get('group')
                    msg_text = payload.get('message')
                    print(f"[{group} | {sender}]: {msg_text}")
                elif command == "ERROR":
                    # TODO: Show an error popup in your GUI
                    print(f"[SERVER ERROR] {payload}")

            except json.JSONDecodeError:
                print("Received invalid JSON.")
            except Exception as e:
                print(f"[RECEIVE ERROR] {e}")
                self.connected = False
        
        self.client_socket.close()
        print("Listener thread stopped.")

    # --- Public functions for your GUI to call ---
    
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

# --- Example of how to run the client (without a GUI) ---
if __name__ == "__main__":
    client = ChatClient()
    client.connect('127.0.0.1', 12345)
    
    # Wait for connection
    time.sleep(1) 
    
    if client.connected:
        # Example flow
        client.login("Alice")
        time.sleep(1) # Give server time to process
        
        client.create_group("Tech_Talk")
        time.sleep(1)
        
        client.send_group_message("Tech_Talk", "Hi everyone!")
        
        # Keep the main thread alive to let the listener work
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Disconnecting...")