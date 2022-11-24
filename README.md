# WeCloud
In this project I created a data cloud server which one can backup data online from different users and locations.<br/>
The server is cross platformed, which means it can work on Windows or Linux.<br/>
## Technologies and main dependencies

- Python
- WatchDog
- Networking Concepts (TCP / UDP)


## Prerequisites

You need to install first:
- Python 3.8
- WatchDog:
```
pip install watchdog
```

## Get the code

Use these commands:

```
git clone https://github.com/roeige/WeCloud.git
cd WeCloud
```

##Run

run these commands:
```
To run the server:
  python3 server.py #server_port
To run the client from anycomputer:
    #1st Argument: IP adress
    #2nd Argument: Server's port.
    #3rd Argument: Path to the folder
    #4th Argument: Time to address the server.
    #5th Argument(optional): key to the folder in the server.
  python3 client.py #1 #2 #3 ...
```

Enjoy!

 
