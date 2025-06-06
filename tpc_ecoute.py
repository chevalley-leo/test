import socket

HOST = ''  # écoute sur toutes les interfaces
PORT = 5001  # choisis un port libre
SAVE_PATH = '/home/c05pc13/Documents/gcodes/dxf3.dxf'  # adapte ce chemin

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"En attente de connexion sur le port {PORT}...")
    while True:
        conn, addr = s.accept()
        with conn:
            print('Connecté par', addr)
            with open(SAVE_PATH, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    f.write(data)
            print("Fichier reçu et sauvegardé.")