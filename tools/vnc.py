#!/usr/bin/env python3
"""Minimal RFB client for the AMX panel.
Usage: vnc.py shot out.png
       vnc.py tap X Y [out.png]
       vnc.py swipe X1 Y1 X2 Y2 [out.png]
       vnc.py type "text" [out.png]
       vnc.py key NAME [out.png]   (enter, back, home, tab, esc, backspace)
Coordinates are in framebuffer pixels."""
import socket, struct, sys, time
from PIL import Image

HOST, PORT = '192.168.1.106', 5900
KEYS = {'enter': 0xff0d, 'back': 0xff1b, 'esc': 0xff1b, 'home': 0xff50,
        'tab': 0xff09, 'backspace': 0xff08, 'up': 0xff52, 'down': 0xff54,
        'left': 0xff51, 'right': 0xff53}

def recvn(s, n):
    b = bytearray()
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise EOFError
        b += c
    return bytes(b)

class VNC:
    def __init__(self):
        s = self.s = socket.create_connection((HOST, PORT), timeout=20)
        recvn(s, 12); s.sendall(b'RFB 003.008\n')
        n = recvn(s, 1)[0]; types = recvn(s, n)
        assert 1 in types, types
        s.sendall(b'\x01')
        assert struct.unpack('>I', recvn(s, 4))[0] == 0, 'auth failed'
        s.sendall(b'\x01')  # shared
        self.w, self.h = struct.unpack('>HH', recvn(s, 4))
        recvn(s, 16)
        nl = struct.unpack('>I', recvn(s, 4))[0]; recvn(s, nl)
        # 32bpp, depth 24, little endian, true colour, RGB shifts 16/8/0
        s.sendall(struct.pack('>BxxxBBBBHHHBBBxxx', 0, 32, 24, 0, 1, 255, 255, 255, 16, 8, 0))
        s.sendall(struct.pack('>BxHi', 2, 1, 0))  # encodings: raw only

    def shot(self, path):
        s = self.s
        s.sendall(struct.pack('>BBHHHH', 3, 0, 0, 0, self.w, self.h))
        img = Image.new('RGB', (self.w, self.h))
        while True:
            t = recvn(s, 1)[0]
            if t == 0:
                recvn(s, 1); nr = struct.unpack('>H', recvn(s, 2))[0]
                for _ in range(nr):
                    x, y, w, h, enc = struct.unpack('>HHHHi', recvn(s, 12))
                    assert enc == 0, enc
                    data = recvn(s, w * h * 4)
                    img.paste(Image.frombuffer('RGB', (w, h), data, 'raw', 'BGRX', 0, 1), (x, y))
                break
            elif t == 1:
                recvn(s, 3); n = struct.unpack('>H', recvn(s, 2))[0]; recvn(s, n * 6)
            elif t == 2:
                pass
            elif t == 3:
                recvn(s, 3); n = struct.unpack('>I', recvn(s, 4))[0]; recvn(s, n)
        img.save(path)
        print(f'saved {path} ({self.w}x{self.h})')

    def ptr(self, mask, x, y):
        self.s.sendall(struct.pack('>BBHH', 5, mask, x, y))

    def tap(self, x, y):
        self.ptr(0, x, y); time.sleep(0.05)
        self.ptr(1, x, y); time.sleep(0.12)
        self.ptr(0, x, y)

    def swipe(self, x1, y1, x2, y2, steps=15):
        self.ptr(1, x1, y1)
        for i in range(1, steps + 1):
            time.sleep(0.03)
            self.ptr(1, x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps)
        time.sleep(0.1); self.ptr(0, x2, y2)

    def key(self, sym):
        self.s.sendall(struct.pack('>BBxxI', 4, 1, sym)); time.sleep(0.03)
        self.s.sendall(struct.pack('>BBxxI', 4, 0, sym)); time.sleep(0.03)

if __name__ == '__main__':
    a = sys.argv[1:]; v = VNC(); out = None
    if a[0] == 'shot':
        out = a[1]
    elif a[0] == 'tap':
        v.tap(int(a[1]), int(a[2])); out = a[3] if len(a) > 3 else None
    elif a[0] == 'swipe':
        v.swipe(*map(int, a[1:5])); out = a[5] if len(a) > 5 else None
    elif a[0] == 'type':
        for ch in a[1]:
            v.key(ord(ch))
        out = a[2] if len(a) > 2 else None
    elif a[0] == 'key':
        v.key(KEYS[a[1]]); out = a[2] if len(a) > 2 else None
    if out:
        time.sleep(1.5); v.shot(out)
