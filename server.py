import socket
import threading
import json

HOST = '0.0.0.0'  # Listen on all network interfaces
PORT = 12345

# --- Shared Data Structures (Protected by a Lock) ---
clients = {}  # {username: client_socket}
groups = {}   # {group_name: [username1, username2, ...]}
data_lock = threading.Lock()

# --- Helper Functions ---

def broadcast_user_list():
    """ (R4) Broadcasts the current user list to all clients. """
    with data_lock:
        user_list = list(clients.keys())
    
    msg = {"command": "UPDATE_USER_LIST", "payload": user_list}
    broadcast(msg)

def broadcast_group_list():
    """ (R9) Broadcasts the current group list to all clients. """
    with data_lock:
        # We must serialize the groups data to send over JSON
        group_list_payload = groups.copy()
        
    msg = {"command": "UPDATE_GROUP_LIST", "payload": group_list_payload}
    broadcast(msg)

def broadcast(message_data):
    """ Helper to send a JSON message to all connected clients. """
    message_json = json.dumps(message_data) + '\n'
    
    with data_lock:
        for client_socket in clients.values():
            try:
                client_socket.sendall(message_json.encode('utf-8'))
            except Exception as e:
                print(f"[Broadcast Error] {e}")

def send_to_client(client_socket, message_data):
    """ Helper to send a JSON message to a specific client. """
    try:
        message_json = json.dumps(message_data) + '\n'
        client_socket.sendall(message_json.encode('utf-8'))
    except Exception as e:
        print(f"[Send Error] {e}")

# --- Main Client Handler ---

def handle_client(client_socket, addr):
    """
    This function runs in its own thread for each connected client.
    """
    print(f"[NEW CONNECTION] {addr} connected.")
    username = None
    
    try:
        # Use makefile for easy line-by-line reading
        client_reader = client_socket.makefile('r', encoding='utf-8')
        
        while True:
            line = client_reader.readline()
            if not line:
                break  # Client disconnected
                
            try:
                message = json.loads(line)
                command = message.get('command')
                payload = message.get('payload')

                # --- R3: Unique Name (Login) ---
                if command == "LOGIN":
                    with data_lock:
                        if payload and payload not in clients:
                            username = payload
                            clients[username] = client_socket
                            print(f"[LOGIN] {addr} is now {username}")
                        else:
                            # Send error and disconnect
                            send_to_client(client_socket, {"command": "ERROR", "payload": "Username taken or invalid."})
                            break
                    
                    broadcast_user_list() # R4
                    broadcast_group_list() # R9

                # Must be logged in for other commands
                if not username:
                    continue

                # --- R7: Private Message ---
                elif command == "MSG_PRIVATE":
                    recipient = payload.get('recipient')
                    msg_text = payload.get('message')
                    
                    with data_lock:
                        recipient_socket = clients.get(recipient)
                        
                    if recipient_socket:
                        msg_data = {"command": "RECV_PRIVATE", "payload": {"sender": username, "message": msg_text}}
                        # Only send to the recipient. The sender's GUI will handle its own display.
                        send_to_client(recipient_socket, msg_data)
                    else:
                        # (Optional) Tell sender the user is offline
                        err_data = {"command": "ERROR", "payload": f"User '{recipient}' is not online."}
                        send_to_client(client_socket, err_data)
                    
                # --- R8: Create Group ---
                elif command == "CREATE_GROUP":
                    group_name = payload
                    with data_lock:
                        if group_name not in groups:
                            groups[group_name] = [username] # Creator is first member
                    broadcast_group_list() # R9
                
                # --- R10: Join Group ---
                elif command == "JOIN_GROUP":
                    group_name = payload
                    with data_lock:
                        if group_name in groups:
                            if username not in groups[group_name]:
                                groups[group_name].append(username)
                    broadcast_group_list() # R9

                # --- R11: Group Message ---
                elif command == "MSG_GROUP":
                    group_name = payload.get('group')
                    msg_text = payload.get('message')
                    
                    with data_lock:
                        members = groups.get(group_name, [])
                        
                    if username in members:
                        msg_data = {"command": "RECV_GROUP", 
                                    "payload": {"sender": username, "group": group_name, "message": msg_text}}
                        
                        # Send to all members in the group
                        with data_lock:
                            for member in members:
                                member_socket = clients.get(member)
                                if member_socket:
                                    send_to_client(member_socket, msg_data)

            except json.JSONDecodeError:
                print(f"[ERROR] Invalid JSON from {addr}")
            except Exception as e:
                print(f"[HANDLER ERROR] {e}")

    except ConnectionResetError:
        print(f"[DISCONNECT] {addr} ({username}) disconnected unexpectedly.")
    finally:
        # --- Client Disconnection Cleanup ---
        if username:
            with data_lock:
                clients.pop(username, None)
                # Remove user from all groups
                for group in groups.values():
                    if username in group:
                        group.remove(username)
            
            print(f"[DISCONNECT] {username} has logged out.")
            broadcast_user_list() # R4
            broadcast_group_list() # R9
            
        client_socket.close()

# --- Server Main Function ---
def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[*] Listening on {HOST}:{PORT}")

    while True:
        client_socket, addr = server_socket.accept()
        # Start a new thread for each client
        thread = threading.Thread(target=handle_client, args=(client_socket, addr))
        thread.daemon = True # Allows server to exit even if threads are running
        thread.start()

if __name__ == "__main__":
    main()