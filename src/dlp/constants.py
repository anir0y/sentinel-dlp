"""Registry paths, GUIDs, and default values for DLP operations."""

# Windows Registry Paths
USBSTOR_KEY_PATH = r"SYSTEM\CurrentControlSet\Services\USBSTOR"

REMOVABLE_STORAGE_POLICY_PATH = (
    r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices"
    r"\{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}"
)

DEVICE_INSTALL_RESTRICTIONS_PATH = (
    r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions"
)

SRP_CODE_IDENTIFIERS_PATH = (
    r"SOFTWARE\Policies\Microsoft\Windows\Safer\CodeIdentifiers"
)

# USB Storage class GUID
USB_STORAGE_CLASS_GUID = "{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}"

# USBSTOR Start values
USBSTOR_DISABLED = 4
USBSTOR_ENABLED = 3

# SRP SaferFlags
SAFER_LEVEL_DISALLOWED = 0
SAFER_LEVEL_UNRESTRICTED = 0x00040000

# Common USB Vendor IDs for fingerprinting
VENDOR_DB: dict[str, str] = {
    "03f0": "HP",
    "0451": "Texas Instruments",
    "046d": "Logitech",
    "04b3": "IBM",
    "04ca": "Lite-On Technology",
    "04d9": "Holtek Semiconductor",
    "04e8": "Samsung Electronics",
    "04f2": "Chicony Electronics",
    "04f3": "Elan Microelectronics",
    "0557": "ATEN International",
    "058f": "Alcor Micro",
    "05ac": "Apple",
    "05e3": "Genesys Logic",
    "0718": "Imation",
    "0781": "SanDisk",
    "0930": "Toshiba",
    "0951": "Kingston Technology",
    "09da": "A4Tech",
    "0b95": "ASIX Electronics",
    "0bda": "Realtek Semiconductor",
    "0cf3": "Qualcomm Atheros",
    "0d8c": "C-Media Electronics",
    "1058": "Western Digital",
    "1307": "Transcend Information",
    "13fe": "Phison Electronics",
    "148f": "Ralink Technology",
    "1532": "Razer",
    "17ef": "Lenovo",
    "1a2c": "China Resource Semico",
    "1bcf": "Sunplus Innovation",
    "1d6b": "Linux Foundation",
    "2109": "VIA Labs",
    "2357": "TP-Link",
    "258a": "SINO WEALTH Electronic",
    "2717": "Xiaomi",
    "413c": "Dell",
    "8086": "Intel",
    "8087": "Intel (Hub)",
}

# ---------------------------------------------------------------------------
# Rubber Ducky / BadUSB detection
# ---------------------------------------------------------------------------

# Known malicious HID device VID:PID pairs.
# Key = "vid:pid" (lowercase hex, no 0x prefix).
# Value = (device_name, threat_description).
KNOWN_DUCKY_DEVICES: dict[str, tuple[str, str]] = {
    # Hak5 USB Rubber Ducky (original & Mark II)
    "03eb:2401": ("Hak5 USB Rubber Ducky", "Keystroke injection attack tool"),
    "03eb:2402": ("Hak5 Rubber Ducky (DFU)", "Ducky in firmware update mode"),
    "03eb:2403": ("Hak5 USB Rubber Ducky MkII", "Keystroke injection attack tool"),
    # Hak5 Bash Bunny
    "f000:ff01": ("Hak5 Bash Bunny", "Multi-vector attack platform (HID+storage+network)"),
    "f000:ff02": ("Hak5 Bash Bunny Mark II", "Multi-vector attack platform"),
    # O.MG Cable / O.MG Plug
    "2e8a:0005": ("O.MG Cable/Plug", "Covert keystroke injection cable"),
    "d3c0:d3c0": ("O.MG Cable (alt)", "Covert keystroke injection cable"),
    # USBNinja Cable
    "16c0:27db": ("USBNinja Cable", "Remote-triggered keystroke injection cable"),
    # CJMCU BadUSB (Beetle-style boards)
    "1b4f:9206": ("CJMCU BadUSB / SparkFun Pro Micro", "Arduino-based HID attack board"),
    # Digispark ATtiny85 (commonly used for BadUSB payloads)
    "16d0:0753": ("Digispark ATtiny85", "Programmable HID injection device"),
    # Maltronics WiFi Ducky
    "1b4f:9207": ("Maltronics WiFi Ducky", "WiFi-triggered keystroke injection"),
    # Generic Atmel DFU / AT32UC3 (Rubber Ducky chipset)
    "03eb:2ff4": ("Atmel AT32UC3 DFU", "Rubber Ducky bootloader chipset"),
    "03eb:2ff0": ("Atmel DFU Device", "Common BadUSB bootloader"),
    "03eb:2fe4": ("Atmel ATMEGA32U4 DFU", "Common BadUSB microcontroller"),
    # Teensy boards (frequently used for BadUSB)
    "16c0:0486": ("Teensy (HID)", "Teensy board in HID mode — common BadUSB platform"),
    "16c0:0478": ("Teensy (Serial+HID)", "Teensy composite — potential BadUSB"),
    # Raspberry Pi Pico in USB HID mode
    "2e8a:0003": ("RPi Pico (HID)", "Raspberry Pi Pico as HID — potential ducky script host"),
    # MalDuino
    "1d50:6108": ("MalDuino", "Open-source keystroke injection tool"),
    # Rubber Ducky clones using generic Holtek HID
    "04d9:1702": ("Holtek Generic Keyboard (clone)", "Common clone chipset used by Ducky knockoffs"),
}

# VIDs frequently associated with DIY/attack HID devices.
# These are NOT auto-blocked but elevate risk when the device claims to be
# a keyboard yet has suspicious characteristics.
SUSPICIOUS_HID_VIDS: set[str] = {
    "03eb",  # Atmel (Rubber Ducky, DFU loaders)
    "16c0",  # Teensy / Van Ooijen Technische Informatica
    "2e8a",  # Raspberry Pi (Pico HID)
    "1b4f",  # SparkFun / CJMCU clones
    "16d0",  # MCS / Digispark
    "1d50",  # OpenMoko / MalDuino
    "f000",  # Hak5 reserved range
    "d3c0",  # O.MG reserved
    "2341",  # Arduino (legitimate but used in attack tooling)
    "1fc9",  # NXP (LPC-based HID injectors)
}

# Product name substrings that indicate a potential rubber ducky / BadUSB.
# Matched case-insensitively against the device's product name and
# manufacturer string.
DUCKY_NAME_KEYWORDS: list[str] = [
    "rubber ducky",
    "bash bunny",
    "badusb",
    "hid attack",
    "ducky",
    "o.mg",
    "usbninja",
    "malduino",
    "wifi ducky",
    "keystroke injection",
    "payload",
    "digispark",
    "teensy",
]

# macOS disk monitoring poll interval (seconds)
DARWIN_POLL_INTERVAL = 2.0
