import serial
import time
from enum import Enum

class XKC_KL200_Error(Enum):
    """Fehlercodes für die XKC_KL200 Klasse"""
    SUCCESS = 0
    INVALID_PARAMETER = 1
    TIMEOUT = 2
    CHECKSUM_ERROR = 3
    RESPONSE_ERROR = 4

class XKC_KL200:
    """
    Klasse zur Steuerung des XKC-KL200-2M-UART Laser-Abstandssensors
    """
    
    def __init__(self, port, baudrate=9600, timeout=1.0):
        """
        Initialisiert den XKC-KL200 Sensor
        
        Args:
            port (str): Serieller Port (z.B. '/dev/ttyUSB0', 'COM3')
            baudrate (int): Baudrate für die serielle Kommunikation (Standard: 9600)
            timeout (float): Timeout für serielle Operationen in Sekunden (Standard: 1.0)
        """
        self._serial = serial.Serial(port, baudrate, timeout=timeout)
        self._available = False
        self._distance = 0
        self._last_received_distance = 0
        self._auto_mode = False
        time.sleep(0.1)  # Kurze Pause für die Initialisierung des Sensors
    
    def close(self):
        """Schließt die serielle Verbindung"""
        if self._serial.is_open:
            self._serial.close()
    
    def hard_reset(self):
        """
        Setzt den Sensor auf Werkseinstellungen zurück
        
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        # Befehl zum Zurücksetzen auf Werkseinstellungen (Xingkechuang default)
        command = bytearray([0x62, 0x39, 0x09, 0xFF, 0xFF, 0xFF, 0xFF, 0xFE, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x39)
    
    def soft_reset(self):
        """
        Setzt den Sensor auf Benutzereinstellungen zurück
        
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        # Befehl zum Zurücksetzen auf Benutzereinstellungen
        command = bytearray([0x62, 0x39, 0x09, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x39)
    
    def change_address(self, address):
        """
        Ändert die Adresse des Sensors
        
        Args:
            address (int): Neue Adresse (0-65534)
            
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        if address > 0xFFFE:
            return XKC_KL200_Error.INVALID_PARAMETER
        
        # Befehl zum Ändern der Adresse
        command = bytearray([0x62, 0x32, 0x09, 0xFF, 0xFF, (address >> 8) & 0xFF, address & 0xFF, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x32)
    
    def change_baud_rate(self, baud_rate):
        """
        Ändert die Baudrate des Sensors
        
        Args:
            baud_rate (int): Baudrate-Index (0-9, siehe Dokumentation)
                0=2400, 1=4800, 2=9600, 3=14400, 4=19200, 5=38400,
                6=56000, 7=57600, 8=115200, 9=128000
                
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        if baud_rate > 9:
            return XKC_KL200_Error.INVALID_PARAMETER
        
        # Befehl zum Ändern der Baudrate
        command = bytearray([0x62, 0x30, 0x09, 0xFF, 0xFF, 0x00, baud_rate, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x30)
    
    def set_upload_mode(self, auto_upload):
        """
        Setzt den Upload-Modus des Sensors
        
        Args:
            auto_upload (bool): True für automatischen Upload, False für manuellen Abfragemodus
            
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        self._auto_mode = auto_upload
        mode = 1 if auto_upload else 0
        
        # Befehl zum Setzen des Upload-Modus
        command = bytearray([0x62, 0x34, 0x09, 0xFF, 0xFF, 0x00, mode, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x34)
    
    def set_upload_interval(self, interval):
        """
        Setzt das Upload-Intervall im automatischen Modus
        
        Args:
            interval (int): Intervall (1-100, entspricht 100ms-10s)
            
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        if interval < 1 or interval > 100:
            return XKC_KL200_Error.INVALID_PARAMETER
        
        # Befehl zum Setzen des Upload-Intervalls
        command = bytearray([0x62, 0x35, 0x09, 0xFF, 0xFF, 0x00, interval, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x35)
    
    def set_led_mode(self, mode):
        """
        Konfiguriert das Verhalten der LED
        
        Args:
            mode (int): 0=an bei Erkennung, 1=aus bei Erkennung, 2=immer aus, 3=immer an
            
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        if mode > 3:
            return XKC_KL200_Error.INVALID_PARAMETER
        
        # Befehl zum Setzen des LED-Modus
        command = bytearray([0x62, 0x37, 0x09, 0xFF, 0xFF, 0x00, mode, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x37)
    
    def set_relay_mode(self, mode):
        """
        Konfiguriert das Verhalten des Relais-Ausgangs
        
        Args:
            mode (int): 0=aktiv bei Erkennung, 1=inaktiv bei Erkennung
            
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        if mode > 1:
            return XKC_KL200_Error.INVALID_PARAMETER
        
        # Befehl zum Setzen des Relais-Modus
        command = bytearray([0x62, 0x38, 0x09, 0xFF, 0xFF, 0x00, mode, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x38)
    
    def set_communication_mode(self, mode):
        """
        Setzt den Kommunikationsmodus des Sensors
        
        Args:
            mode (int): 0=Relais-Modus, 1=UART-Modus
            
        Returns:
            XKC_KL200_Error: SUCCESS bei Erfolg, sonst Fehlercode
        """
        if mode > 1:
            return XKC_KL200_Error.INVALID_PARAMETER
        
        # Befehl zum Setzen des Kommunikationsmodus
        command = bytearray([0x61, 0x30, 0x09, 0xFF, 0xFF, 0x00, mode, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        return self._wait_for_response(0x30)
    
    def read_distance(self, timeout=1.0):
        """
        Liest die aktuelle Distanz vom Sensor im manuellen Modus
        
        Args:
            timeout (float): Timeout in Sekunden (Standard: 1.0)
            
        Returns:
            int: Gemessene Distanz in mm oder 0 bei Fehler
        """
        if self._auto_mode:
            # Im automatischen Modus sollte process_auto_data() verwendet werden
            return self._last_received_distance
        
        # Befehl zum Lesen der Distanz
        command = bytearray([0x62, 0x33, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
        command[8] = self._calculate_checksum(command[:8])
        self._send_command(command)
        
        # Auf Antwort warten mit Timeout
        start_time = time.time()
        while self._serial.in_waiting < 9:
            if time.time() - start_time > timeout:
                return self._last_received_distance  # Timeout, letzte bekannte Distanz zurückgeben
            time.sleep(0.01)
        
        # Antwort lesen und verarbeiten
        response = self._serial.read(9)
        
        if response[0] == 0x62 and response[1] == 0x33:
            length = response[2]
            address = (response[3] << 8) | response[4]
            raw_distance = (response[5] << 8) | response[6]
            checksum = response[8]
            calc_checksum = self._calculate_checksum(response[:8])
            
            if checksum == calc_checksum:
                self._distance = raw_distance
                self._last_received_distance = raw_distance
                self._available = True
                return self._distance
        
        # Bei Fehler letzte bekannte Distanz zurückgeben
        return self._last_received_distance
    
    def available(self):
        """
        Prüft, ob neue Daten im automatischen Modus verfügbar sind
        
        Returns:
            bool: True wenn neue Daten verfügbar sind, sonst False
        """
        # Prüfen, ob neue Daten im automatischen Modus verfügbar sind
        if self._auto_mode and self._serial.in_waiting >= 9:
            return True
        return self._available
    
    def process_auto_data(self):
        """
        Verarbeitet eingehende Daten im automatischen Modus
        
        Returns:
            bool: True wenn neue Daten erfolgreich verarbeitet wurden, sonst False
        """
        if not self._auto_mode or self._serial.in_waiting < 9:
            return False
        
        # Daten aus dem seriellen Buffer lesen
        response = self._serial.read(9)
        
        # Prüfen, ob es sich um eine gültige Distanzmeldung handelt
        if response[0] == 0x62 and response[1] == 0x33:
            length = response[2]
            address = (response[3] << 8) | response[4]
            raw_distance = (response[5] << 8) | response[6]
            checksum = response[8]
            calc_checksum = self._calculate_checksum(response[:8])
            
            if checksum == calc_checksum:
                self._distance = raw_distance
                self._last_received_distance = raw_distance
                self._available = True
                return True
        
        # Ungültige Daten aus dem Buffer entfernen
        if self._serial.in_waiting > 0:
            self._serial.read(1)
        return False
    
    def get_distance(self):
        """
        Gibt die zuletzt gemessene Distanz zurück
        
        Returns:
            int: Zuletzt gemessene Distanz in mm
        """
        self._available = False
        return self._distance
    
    def get_last_received_distance(self):
        """
        Gibt die zuletzt empfangene Distanz zurück (ohne _available zurückzusetzen)
        
        Returns:
            int: Zuletzt empfangene Distanz in mm
        """
        return self._last_received_distance
    
    def _send_command(self, command):
        """
        Sendet einen Befehl an den Sensor
        
        Args:
            command (bytearray): Befehlsarray
        """
        self._serial.write(command)
        self._serial.flush()
    
    def _calculate_checksum(self, data):
        """
        Berechnet die XOR-Prüfsumme für einen Befehl
        
        Args:
            data (bytes or bytearray): Datenarray
            
        Returns:
            int: Berechnete Prüfsumme
        """
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum
    
    def _wait_for_response
