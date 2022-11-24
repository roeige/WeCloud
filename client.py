import os
import sys
import utils
import socket
import time

import watchdog.events
import watchdog.observers
import watchdog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

client_id = None
client_instance_id = '-1'
client_socket = None
client_rcv_buff = []

server_ip = None
server_port = None
client_dir = None
wd_time = None

# =======================================
#               Watchdog
# =======================================

# Queue of events to push to server at next contact period
event_push_queue = []
blacklist = []


class OnMyWatch:
    # Set the directory on watch
    # watchDirectory = client_dir

    def __init__(self):

        self.observer = Observer()

    def run(self):
        global watch_dog_switch, blacklist
        event_handler = Handler()
        self.observer.schedule(event_handler, client_dir, recursive=True)
        self.observer.start()
        try:
            while True:
                open_connection()  # Open connection to server
                # Identify ourselves to the server
                utils.send_token(client_socket, ['identify', client_id, client_instance_id])

                blacklist.extend(request_updates('pull_changes'))
                flush_push_event_queue()
                close_connection()  # Close connection

                time.sleep(wd_time)
        except:
            self.observer.stop()

        self.observer.join()


class Handler(FileSystemEventHandler):
    @staticmethod
    def on_any_event(event):
        global event_push_queue

        file_name = event.src_path.split(os.path.sep)[-1]

        # Get relative path of file/dir
        relative_path = event.src_path[len(client_dir) + 1:]

        # Ignore hidden files
        if relative_path.startswith('.') or relative_path.find(os.path.sep + '.') >= 0:
            return

        if event.event_type == 'created':

            if os.path.isdir(event.src_path):
                event_push_queue.append(('mkdir', relative_path))
            else:
                event_push_queue.append(('mkfile', event.src_path, relative_path))

        elif event.event_type == 'moved':

            relative_dest_path = event.dest_path[len(client_dir) + len(os.path.sep):]
            # utils.send_token(client_socket, ['mov', relative_path, relative_dest_path])

            old_object_is_created = False

            for i in range(len(event_push_queue) - 1, -1, -1):
                ev = event_push_queue[i]
                # If event mentions the object that was moved
                if ev[1].find(relative_path) >= 0:
                    # If the event is a make event
                    if ev[0].startswith('mk'):
                        old_object_is_created = True
                        event_push_queue.pop(i)  # Remove
                    break

            # If object wasn't created in the same sleep interval
            if not old_object_is_created:
                event_push_queue.append(('mov', relative_path, relative_dest_path))
            else:
                new_full_path = os.path.join(client_dir, relative_dest_path)
                new_rel_path = relative_dest_path
                event_push_queue.append(('mkfile', new_full_path, new_rel_path))

        elif event.event_type == 'deleted':

            if event.is_directory:
                event_push_queue.append(('rmdir', relative_path))
                # utils.send_token(client_socket, ['rmdir', relative_path])
            else:
                event_push_queue.append(('rmfile', relative_path))
                # utils.send_token(client_socket, ['rmfile', relative_path])

        # For modified events, ignore directories
        elif event.event_type == 'modified' and not event.is_directory:

            # Convert 'modfile' to remove + create
            mkfile_cmd = ('mkfile', event.src_path, relative_path)
            if mkfile_cmd not in event_push_queue and mkfile_cmd not in blacklist:
                event_push_queue.append(('rmfile', relative_path))
                event_push_queue.append(('mkfile', event.src_path, relative_path))


def flush_push_event_queue():
    for item in event_push_queue:
        if item in blacklist:

            blacklist.remove(item)
        else:

            if item[0] == 'mkfile':
                utils.send_file(client_socket, 'mkfile', item[1], item[2])
            elif item[0] == 'mov':
                utils.send_token(client_socket, [item[0], item[1], item[2]])
            else:
                utils.send_token(client_socket, [item[0], item[1]])
    event_push_queue.clear()


# ==========  END WATCHDOG  ==========

def open_connection():
    global client_socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, server_port))


#
def close_connection():
    utils.send_token(client_socket, ['fin'])
    client_socket.close()


def login_procedure():
    global client_id
    global client_instance_id
    global client_rcv_buff

    if len(sys.argv) == 5:

        # Tell server we are completely new and get new ID and instance num
        utils.send_token(client_socket, ['identify', '-1', '-1'])
        client_rcv_buff, client_id = utils.get_token(client_socket, client_rcv_buff)
        client_rcv_buff, client_instance_id = utils.get_token(client_socket, client_rcv_buff)
        # get all files and dirs from current file(if there are such files)
        # send all the files to the server.
        dir_arr, file_arr = utils.get_dirs_and_files(client_dir)
        # send all files and dirs (if they exist):
        utils.send_all_dirs_and_files(client_socket, dir_arr, file_arr, client_dir)


    elif len(sys.argv) == 6:
        client_id = sys.argv[5]

        utils.send_token(client_socket, ['identify', client_id, '-1'])
        client_rcv_buff, client_instance_id = utils.get_token(client_socket, client_rcv_buff)

        # Download entire directory from the cloud
        request_updates('pull_all')


def request_updates(pull_type):
    global client_rcv_buff

    server_directives = []

    utils.send_token(client_socket, [pull_type])
    while True:
        client_rcv_buff, cmd_token = utils.get_token(client_socket, client_rcv_buff)
        if cmd_token == 'eoc':
            break
        server_directive = handle_server_directive(cmd_token)
        server_directives.extend(server_directive)

    return server_directives


def handle_server_directive(cmd_token):
    global client_rcv_buff

    if cmd_token == 'mkfile':
        # Name of directory/file
        client_rcv_buff, file_name = utils.get_token(client_socket, client_rcv_buff)
        file_name = utils.system_path(file_name)
        # Creare file
        abs_path = os.path.join(client_dir, file_name)
        utils.create_file(abs_path)
        # Receive file data
        utils.rcv_file(client_socket, client_rcv_buff, abs_path)
        # Return partial blacklist
        return [(cmd_token, abs_path, file_name)]

    elif cmd_token == 'mkdir' or cmd_token == 'rmdir' or cmd_token == 'rmfile':
        # Name of directory/file
        client_rcv_buff, dir_name = utils.get_token(client_socket, client_rcv_buff)
        dir_name = utils.system_path(dir_name)
        # Creare dir
        abs_path = os.path.join(client_dir, dir_name)
        # Delete directory or file accordingly
        if cmd_token == 'mkdir':
            if not os.path.exists(abs_path):
                os.mkdir(abs_path)
        elif cmd_token == 'rmdir':
            utils.deep_delete(abs_path)
        #            os.rmdir(abs_path)
        elif cmd_token == 'rmfile':
            utils.remove_file(abs_path)
        # Return partial blacklist
        return [(cmd_token, dir_name)]

    elif cmd_token == 'modfile':
        client_rcv_buff, file_name = utils.get_token(client_socket, client_rcv_buff)
        # Convert 'modfile' to remove + create
        client_rcv_buff.insert(0, 'rmfile')
        client_rcv_buff.insert(1, file_name)
        client_rcv_buff.insert(2, 'mkfile')
        client_rcv_buff.insert(3, file_name)
    elif cmd_token == 'mov':
        # Get relative paths of both src and dest
        client_rcv_buff, src_path = utils.get_token(client_socket, client_rcv_buff)
        client_rcv_buff, dest_path = utils.get_token(client_socket, client_rcv_buff)
        # Get absolute paths
        src_path = utils.system_path(src_path)
        dest_path = utils.system_path(dest_path)
        abs_src_path = os.path.join(client_dir, src_path)
        abs_dest_path = os.path.join(client_dir, dest_path)
        abs_abs_path = utils.get_abs_path(abs_dest_path)
        # Check if move file is needed
        if not os.path.exists(abs_abs_path):
            # Move the files
            # os.renames(abs_src_path, abs_dest_path)
            utils.move_folder(abs_src_path, abs_dest_path)
        # Return blacklist
        return [(cmd_token, src_path, dest_path), ('mkfile', dest_path), ('rmfile', src_path)]


def on_start_up():
    # Get input args
    global server_ip, server_port, client_dir, wd_time
    if len(sys.argv) < 5 or len(sys.argv) > 6:
        print('Invalid number of arguments, terminating program.')
        sys.exit(1)

    # VALIDATE INPUT
    server_ip = utils.validate_ip(sys.argv[1])
    server_port = utils.validate_port(sys.argv[2])
    client_dir = sys.argv[3]
    client_dir = utils.system_path(client_dir)
    wd_time = int(sys.argv[4])

    if server_ip is None or server_port is None:
        sys.exit(1)
    # Validate wd_time
    if wd_time <= 0:
        print('Sleep period must be a positive whole number')
        sys.exit(1)

    # Make folder if doesn't exist
    if not os.path.exists(client_dir):
        os.makedirs(client_dir)

    open_connection()
    login_procedure()
    close_connection()


if __name__ == "__main__":
    # ==========  Enter as Arguments ==========
    # 1st Argument: IP adress
    # 2nd Argument: Server's port.
    # 3rd Argument: Path to the folder
    # 4th Argument: Time to address the server.
    # 5st Argument(optional): key to the folder in the server.
    on_start_up()

    watch = OnMyWatch()
    watch.run()
