"""
tcp_ecoute.py

Description:
    Author: Léo Chevalley
    This script listens for incoming TCP connections on a specified port and saves the received file data to a specified path. It is designed for simple file transfer over a local network.

License:
    MIT License
    Copyright (c) 2025 Léo Chevalley
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import socket

HOST = ''  # Listen on all interfaces
PORT = 5001  # Choose a free port
SAVE_PATH = '/home/c05pc13/Documents/gcodes/dxf3.dxf'  # Path to save the received file

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"Waiting for connection on port {PORT}...")
    while True:
        conn, addr = s.accept()
        with conn:
            print('Connected by', addr)
            # Open the file in binary write mode to save incoming data
            with open(SAVE_PATH, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    f.write(data)
            print("File received and saved.")

