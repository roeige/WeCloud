import socket
import time
import utils
import sys
import random
import string
import os

SERVER_DIR = "server_dir"
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_rcv_buff = []

curr_client_id = None
curr_client_inst = None
global client_socket
global client_addr

# Maps account id to number of instances logged in to that id
instance_count_map = {}
# Maps account id + instance num to unique list of pending updates
changes_map = {}


def generate_id():
    return str(''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=128)))


def identify_new_client():
    global server_rcv_buff, curr_client_id, curr_client_inst, instance_account_map
    # Set client id
    server_rcv_buff, curr_client_id = utils.get_token(client_socket, server_rcv_buff)
    # Set client instance num
    server_rcv_buff, curr_client_inst = utils.get_token(client_socket, server_rcv_buff)
    # New ID and new instance
    if curr_client_id == '-1':
        # Generate and send new ID for client
        new_id = generate_id()
        print(new_id)
        # Add new ID to instance_count_map
        instance_count_map[new_id] = 0
        # Generate new folder for client
        os.makedirs(os.path.join(SERVER_DIR, new_id))
        # Send client new ID
        utils.send_token(client_socket, [new_id, '0'])
        # Update variable
        curr_client_id = new_id
        curr_client_inst = '0'
        # Add new entry to changes map
        changes_map[(curr_client_id, curr_client_inst)] = []
    # Existing ID but new instance
    elif curr_client_inst == '-1':
        # Increase instance count
        instance_count_map[curr_client_id] += 1
        # Get new instance num
        new_inst_id = str(instance_count_map[curr_client_id])
        # Update variable
        curr_client_inst = new_inst_id
        utils.send_token(client_socket, [new_inst_id])
        # Add new entry to changes map
        changes_map[(curr_client_id, curr_client_inst)] = []


def add_change(change):
    for (acc_id, inst_num) in changes_map:
        if acc_id == curr_client_id and inst_num != curr_client_inst:
            changes_map[(acc_id, inst_num)].append(change)


def process_command(cmd_token):
    global server_rcv_buff

    if cmd_token == 'identify':
        identify_new_client()
    elif cmd_token == 'mkfile':
        # Name of file
        server_rcv_buff, file_name = utils.get_token(client_socket, server_rcv_buff)
        file_name = utils.system_path(file_name)
        # Create file
        # return the normal path without redundant additions between systems.
        abs_path = os.path.join(SERVER_DIR, curr_client_id, file_name)
        utils.create_file(abs_path)
        # Receive file data
        utils.rcv_file(client_socket, server_rcv_buff, abs_path)
        # Update changes map
        add_change(('mkfile', abs_path, file_name))

    elif cmd_token == 'mkdir' or cmd_token == 'rmdir' or cmd_token == 'rmfile':
        # Name of directory/file
        server_rcv_buff, dir_name = utils.get_token(client_socket, server_rcv_buff)
        # Creare dir
        dir_name = utils.system_path(dir_name)
        abs_path = os.path.join(SERVER_DIR, curr_client_id, dir_name)
        abs_path=utils.get_abs_path(abs_path)
        # Delete directory or file accordingly
        if cmd_token == 'mkdir':
            if not os.path.exists(abs_path):
                os.makedirs(abs_path)
        elif cmd_token == 'rmdir':
            utils.deep_delete(abs_path)
        #            os.rmdir(abs_path)
        elif cmd_token == 'rmfile':
            utils.remove_file(abs_path)

        # Update changes map
        add_change((cmd_token, dir_name))

    elif cmd_token == 'modfile':
        server_rcv_buff, file_name = utils.get_token(client_socket, server_rcv_buff)
        # Convert 'modfile' to remove + create
        server_rcv_buff.insert(0, 'rmfile')
        server_rcv_buff.insert(1, file_name)
        server_rcv_buff.insert(2, 'mkfile')
        server_rcv_buff.insert(3, file_name)
    elif cmd_token == 'mov':
        # Get relative paths of both src and dest
        server_rcv_buff, src_path = utils.get_token(client_socket, server_rcv_buff)
        server_rcv_buff, dest_path = utils.get_token(client_socket, server_rcv_buff)
        src_path = utils.system_path(src_path)
        dest_path = utils.system_path(dest_path)
        # Get absolute paths
        abs_src_path = os.path.join(SERVER_DIR, curr_client_id, src_path)
        abs_dest_path = os.path.join(SERVER_DIR, curr_client_id, dest_path)
        # Move the files'
        # os.renames(abs_src_path, abs_dest_path)
        utils.move_folder(abs_src_path, abs_dest_path)
        # Update changes map
        add_change(('mov', src_path, dest_path))

    elif cmd_token.startswith('pull'):
        update_client(cmd_token == 'pull_all')


def update_client(send_everything=False):
    # Send all dirs and files (in that order)
    if send_everything:
        client_folder = os.path.join(SERVER_DIR, curr_client_id)
        dirs, files = utils.get_dirs_and_files(client_folder)
        utils.send_all_dirs_and_files(client_socket, dirs, files, client_folder)

    # Only send changes
    else:

        for change in changes_map[(curr_client_id, curr_client_inst)]:
            if change[0] == 'mkfile':
                abs_file_path = change[1]
                rel_file_path = abs_file_path[
                                len(os.path.join(SERVER_DIR, curr_client_id)) + len(os.path.sep):]
                #                rel_file_path = abs_file_path[len(SERVER_DIR + curr_client_id) + len(os.path.sep):]
                utils.send_file(client_socket, 'mkfile', abs_file_path, rel_file_path)
            else:
                args = [change[0], change[1]] if len(change) == 2 else [change[0], change[1], change[2]]

                utils.send_token(client_socket, args)

    # Clear changes map
    changes_map[(curr_client_id, curr_client_inst)].clear()

    # Send eoc
    utils.send_token(client_socket, ['eoc'])


if __name__ == "__main__":
    # GET SERVER PORT
    # Enter the arguments server port
    server_port = utils.validate_port(sys.argv[1])

    if server_port is None:
        sys.exit(1)

    server.bind(('', server_port))
    server.listen()

    # Begin receiving clients
    while True:
        global client_socket
        global client_addr

        client_socket, client_address = server.accept()

        while True:

            server_rcv_buff, cmd_token = utils.get_token(client_socket, server_rcv_buff)

            if cmd_token == 'fin':
                break
            if cmd_token is not None:
                process_command(cmd_token)
        client_socket.close()
