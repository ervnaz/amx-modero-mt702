// XIAO ESP32-S3  —  USB<->TTL serial bridge with runtime baud control.
// Serial  = native USB CDC (to the PC).
// Serial1 = hardware UART on GPIO44 (RX) / GPIO43 (TX)  -> AMX debug header.
//
// Normal bytes pass through transparently in both directions.
// Control from PC: a byte 0x01 ('SOH') starts a command line, terminated by \n:
//     0x01 B 115200 \n     -> set Serial1 baud to 115200
//     0x01 ?        \n     -> print current baud
// Control bytes are NOT forwarded to the AMX, so sweeping baud is safe while listening.

const int RXP = 44;   // D7 on XIAO = GPIO44  (RX  <- AMX TX)
const int TXP = 43;   // D6 on XIAO = GPIO43  (TX  -> AMX RX)
uint32_t curBaud = 115200;
bool inCtl = false;
String ctl;

void setBaud(uint32_t b) {
  Serial1.end();
  delay(5);
  Serial1.begin(b, SERIAL_8N1, RXP, TXP);
  curBaud = b;
  Serial.printf("\r\n[bridge] Serial1 @ %u 8N1\r\n", b);
}

void setup() {
  Serial.begin(115200);           // USB CDC (baud ignored on native USB)
  setBaud(115200);
  delay(50);
  Serial.print("\r\n[XIAO bridge ready]\r\n");
}

void loop() {
  while (Serial.available()) {
    int c = Serial.read();
    if (!inCtl && c == 0x01) { inCtl = true; ctl = ""; continue; }
    if (inCtl) {
      if (c == '\n' || c == '\r') {
        if (ctl.length() >= 1 && ctl[0] == 'B') setBaud((uint32_t) ctl.substring(1).toInt());
        else if (ctl.length() >= 1 && ctl[0] == '?') Serial.printf("\r\n[bridge] cur %u\r\n", curBaud);
        inCtl = false;
      } else ctl += (char)c;
      continue;
    }
    Serial1.write((uint8_t)c);
  }
  while (Serial1.available()) Serial.write((uint8_t)Serial1.read());
}
