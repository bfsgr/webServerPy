from socket import *
import threading
import time
import os
import mimetypes
import re
from pathlib import Path

class ManageGET(threading.Thread):
    def __init__(self, threadID, conn, request):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.conn = conn
        self.request = request

    def returnGET(self, path):
        #At this point there is a file to send, so the response is 200 OK
        header = "HTTP/1.1 200 OK\r\n"
        #writes the connection type in the response
        responseRow = "Connection: " + self.request.connection + "\n"
        #writes current date in GMT
        responseRow += "Date: " + time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()) + "\r\n"
        #writes server name 
        responseRow += "Server: bfsgr (Fedora)\r\n"
        #get the last modified date of the file and write it in GMT
        ltime = os.path.getmtime(path)
        ltime = time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime(ltime))
        responseRow += "Last-Modified: " +  ltime + "\r\n"
        #Writes file size (in bytes)
        responseRow += "Content-Length: " + str(os.path.getsize(path)) + "\r\n"
        #Writes the MIME type 
        responseRow += "Content-Type: " + str(mimetypes.guess_type(path)[0]) + "\r\n\r\n"

        #lock
        sending.acquire()
        #sends header (200 OK)
        self.conn.send(header.encode())
        #sends the rest of the message
        self.conn.send(responseRow.encode())
        #open requested file as ReadOnly in binary
        openFile = open(path, "rb")
        #transfer file data to memory
        data = openFile.read()
        #sent it
        self.conn.send(data)
        #close requested file
        openFile.close()

        #release lock
        sending.release()
        
    def return404(self):
        #404 default message
        response = "HTTP/1.1 404\r\nDate: " + time.strftime("%a, %d %b %Y %H:%M:%S %Z", time.gmtime()) + "\r\n\r\n"
        #Lock, send and release message
        sending.acquire()
        self.conn.send(response.encode())
        sending.release()

    def run(self):
        if not self.request:
            self.return404() #If resquest is 0 then return 404
        else:
            #URL is root?
            if self.request.url == "/":
                #If so look for index.html
                path = Path("./index.html")

                if path.is_file():
                    #directory has index.html file, send it
                    self.returnGET(path)
                else:
                    #index.html not found, send 404
                    self.return404()
            else:
                #URL is not root
                #Attach '.' to the path (current directory)
                path = "." + self.request.url
                path = Path(path)
                #File exists?
                if path.is_file():
                    #send it
                    self.returnGET(path)
                else:
                    #file not found, send 404
                    self.return404()


#Managing Thread all new connections start here
class ManageConnection(threading.Thread):
    #makes the parameters global inside the object
    def __init__(self, threadID, conn):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.conn = conn

    #loads data from the connection
    def load(self, oldBuffs, buffer):
        #Lock, get more data (2048 bytes) and release
        receiving.acquire()
        buffer = self.conn.recv(2048).decode()
        receiving.release()

        #slipt data in an array (by lines)
        buffLines = buffer.splitlines()
        #if the last line is and empty line (Base case)
        if buffLines[len(buffLines)-1] == "":
            #concatenate all past buffers with the current buffer and return
            return oldBuffs+buffer
        else: 
            #the last line isn't empty. Call load again (Recursion)
            return self.load(oldBuffs+buffer, buffer)
    
    #start point of the thread
    def run(self):
        #Lock and get 3 bytes, then release
        receiving.acquire() 
        buff = self.conn.recv(3).decode()
        receiving.release()

        #If the buffer isn't GET then proceed to self 404 message back
        if buff != "GET":
            #Set up a thread that will send a 404 message back
            menage = ManageGET(self.threadID, self.conn, 0)
            menage.start()
            #Wait until it completes
            menage.join()
            #then close the connection
            self.conn.close()
        else:
            #load the rest of the resquest
            buff = self.load(buff, buff)
            #parse the buffer in a HTTPRequest object
            request = HTTPRequest(buff)
            #Set a thread to handle the request
            manage = ManageGET(self.threadID, self.conn, request)
            manage.start()
            #Wait until it completes
            manage.join()
            #then close the connection
            self.conn.close()

#HTTPRequest class, used to keep the request data
class HTTPRequest:
    def __init__(self, data):
        #slipt data in an array (by lines)
        lines = data.splitlines()
        #slipt the first line by its spaces
        requestRow = lines[0].split(' ')
        #The first element is the request type (GET)
        self.rtype = requestRow[0] 
        #The second element is the requested URL
        self.url = requestRow[1] 
        #The last element is the HTTP version 
        self.version = requestRow[2]

        #Match the connection header in the request using a regex
        self.connection = re.search(r'Connection: (.*)', data)
        #If found then:
        if self.connection:
            #set the connection type as the value found in "(.*)"
            self.connection = self.connection.group(1)
        else:
            #if there isn't a connection header, then assume keep-alive
            self.connection = "keep-alive\r"

#configure server port and create socket
serverPort = 35698
serverSocket = socket(AF_INET,SOCK_STREAM)
#option so we don't have to wait to reuse socket port (for debuging)
serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
#bind to server port and start to listen it
serverSocket.bind(('', serverPort))
serverSocket.listen()

#set locks for thread sync
sending = threading.Lock()
receiving = threading.Lock()

#forever 
while True:
    #wait for a connection, if there isn't one, this thread will sleep here
    connection, addr = serverSocket.accept()
    #there is a connection, setting a thread to handle it
    thread = ManageConnection(addr, connection)
    thread.start()

   
