#!/usr/bin/env python3
# Non-blocking serial capture: opens with O_NONBLOCK + sets CLOCAL so it never
# waits on carrier. Reads /dev/ttyUSB0 at 115200 8N1 and writes raw bytes to stdout.
import os, sys, time, termios, fcntl

dev = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
a = termios.tcgetattr(fd)
# iflag oflag cflag lflag ispeed ospeed cc
a[0] = 0                                   # iflag: raw, no xon/xoff, no cr/nl map
a[1] = 0                                   # oflag: raw
a[2] = (a[2] & ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
        | termios.CS8 | termios.CLOCAL | termios.CREAD)   # 8N1, ignore modem, rx on
a[3] = 0                                   # lflag: non-canonical, no echo
a[4] = termios.B115200
a[5] = termios.B115200
a[6][termios.VMIN] = 0
a[6][termios.VTIME] = 0
termios.tcsetattr(fd, termios.TCSANOW, a)
out = sys.stdout.buffer
while True:
    try:
        d = os.read(fd, 4096)
        if d:
            out.write(d); out.flush()
        else:
            time.sleep(0.03)
    except BlockingIOError:
        time.sleep(0.03)
    except OSError:
        time.sleep(0.1)
