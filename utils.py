import socket
import os

MSG_LEN_NUM_BYTES = 8
READ_SPEED = 2 * 2048
SEND_SPEED = 3 * 2048


def remove_file(abs_path):
    # check if file exists:
    if os.path.exists(abs_path):
        # check bugged case remove file but its dir:
        if is_dir(abs_path):
            # need to check if there are recursive files inside this dir,if so we need to delete them aswell.
            deep_delete(abs_path)
        else:
            os.remove(abs_path)


def system_path(path):
    # check if the system is Unix and we came from windows
    if os.name == 'posix':
        return path.replace('\\', '/')
    # if we are in windows use python lib func
    return os.path.normpath(path)


def send_token(socket, args, encode=True):
    # assert len(args) > 0, "send_token: length of args in send_token must be > 0"
    if encode:
        for arg in args:
            encoded = arg.encode('utf-8')
            len_bytes = len(encoded).to_bytes(MSG_LEN_NUM_BYTES, 'little')

            socket.sendall(len_bytes + encoded)
    # in case its pure data and not files or dirs
    else:
        socket.sendall(args[0])
        # socket.sendall(SEP_CHAR.encode())


def is_dir(relative_path):
    abs_path = os.path.normpath(os.path.abspath(relative_path))
    return os.path.isdir(abs_path)


def get_abs_path(path):
    return os.path.normpath(os.path.abspath(path))


def get_token(socket, buff, num_bytes_to_read=-1):
    # If buffer is empty, must read from socket
    if len(buff) == 0:
        if num_bytes_to_read >= 0:
            data = socket.recv(num_bytes_to_read)
            buff.append(data)
        else:
            msg_len = socket.recv(MSG_LEN_NUM_BYTES)
            num_bytes_to_read = int.from_bytes(msg_len, 'little')
            data = socket.recv(num_bytes_to_read)

            try:
                decoded = data.decode('UTF-8')
                buff.append(decoded)
            except:
                buff.append(data)

    # whether its empty or not, we want to return one command_token from the buff list we have 😀'
    if len(buff) > 0:
        #
        return buff, buff.pop(0)
    return buff, None


def send_file(my_socket, cmd, full_file_path, relative_path):
    if not os.path.exists(full_file_path):
        return

    file_size = os.path.getsize(full_file_path)
    send_token(my_socket, [cmd, relative_path, str(file_size)])
    if file_size == 0:
        return

    with open(full_file_path, 'rb') as f:
        data = f.read(SEND_SPEED)
        while len(data) > 0:
            send_token(my_socket, [data], encode=False)
            data = f.read(SEND_SPEED)


def rcv_file(my_socket, my_buff, abs_path):
    my_buff, size = get_token(my_socket, my_buff)

    size = int(size)
    while size > 0:
        chunk_size = min(size, READ_SPEED)
        # size -= chunk_size
        my_buff, data = get_token(my_socket, my_buff, num_bytes_to_read=chunk_size)
        # data = my_socket.recv(chunk_size)
        # Read content and write to file
        size -= len(data)

        write_data(abs_path, data)


def write_data(abs_path, data):
    with open(abs_path, 'ab') as f:
        f.write(data)


def create_file(abs_path):
    f = open(abs_path, 'w')
    f.close()


def remove_last_path_element(path):
    return path.split(os.path.sep)[-1], path[:path.rfind(os.path.sep)]


'''
Returns two arrays, the first containing all of the subdirectories
(of all depths) of top_root, and the second containing all of the files
(of all depths) of top_root. All paths do not begin with top_root.
'''


def get_dirs_and_files(top_root):
    dirs = []
    files = []
    for root, d_names, f_names in os.walk(top_root):
        dirs_then_names = d_names + f_names
        for item in dirs_then_names:
            whole_path = os.path.join(root, item)
            whole_path = whole_path[len(top_root) + len(os.path.sep):]
            if item in d_names:
                dirs.append(whole_path)
            else:
                files.append(whole_path)
    return dirs, files


def send_all_dirs_and_files(socket, dirs, files, dest_folder):
    for rel_path in (dirs + files):
        abs_path = os.path.join(dest_folder, rel_path)
        if rel_path in dirs:
            send_token(socket, ['mkdir', rel_path])
        else:
            send_file(socket, 'mkfile', abs_path, rel_path)


'''
Given a folder, deletes the folders and all elements inside it.
'''


def deep_delete(top_root):
    for root, d_names, f_names in os.walk(top_root, topdown=False):
        for file in f_names:
            os.remove(os.path.join(root, file))
        for folder in d_names:
            os.rmdir(os.path.join(root, folder))
    os.rmdir(top_root)


'''
Moves a folder that is either empty or unempty
'''


def move_folder(move_dir_path, new_path):
    # If folder doesn't exist, return
    if not os.path.exists(move_dir_path):
        return

    # If folder is empty, simply rename it
    if is_folder_empty(move_dir_path):
        os.renames(move_dir_path, new_path)
        return

    # Get name of dir to be moved, as well as path of its parent dir
    move_dir_name, root_dir = remove_last_path_element(move_dir_path)
    # Get parent folder at destination
    _, dest_parent = remove_last_path_element(new_path)

    # Make empty folder at dest location
    os.mkdir(new_path)

    # Loop through contents
    for root, d_names, f_names in os.walk(move_dir_path, topdown=True):
        for file in f_names:
            # Move file
            os.renames(os.path.join(root, file), os.path.join(new_path, file))
        for folder in d_names:
            # Move folder recursively
            move_folder(os.path.join(root, folder), os.path.join(new_path, folder))


def is_folder_empty(dir_path):
    for root, d_names, f_names in os.walk(dir_path, topdown=True):
        if len(d_names) + len(f_names) > 0:
            return False
    return True


# ==============================
# ====  INPUT VERIFICATION  ====
# ==============================


def validate_port(port_num):
    if not port_num.isdigit() or int(port_num) < 1 or int(port_num) > 65535:
        print('Invalid port number')
        return None
    return int(port_num)


def validate_ip(ip_addr):
    try:
        socket.inet_aton(ip_addr)
        # If we got here, IP is legal
        return ip_addr
    except socket.error:
        # IP is illegal
        print('Invalid IP address')
        return None
