"""Constants for the net4home integration."""

from homeassistant.const import Platform

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Domain and network defaults
DOMAIN = "net4home"
DEFAULT_MI = 65281
DEFAULT_OBJADR = 32700
CONF_MI = "MI"
CONF_OBJADR = "OBJADR"

N4H_IP_PORT                         = 3478
N4H_BJ_NAME_BUSCONNECTOR  =  "_n4hbuscon._tcp"
N4H_BJ_NAME_IREMOTESERVER =  "_n4hiremote._tcp"

# Packet types (ptypes)
N4HIP_PT_PAKET = 4001               # n4hPacket
N4HIP_PT_PASSWORT_REQ = 4012        # Password handshake request
N4HIP_PT_OOB_DATA_RAW = 4010        # Out-of-band data

# Security handshake response codes
# NOTE: Verify these values against your Busconnector configuration
N4H_IP_CLIENT_ACCEPTED = 0          # client accepted (placeholder)
N4H_IP_CLIENT_DENIED_WRONG_PASSWORD = -700  # wrong password
N4H_IP_CLIENT_DENIED_WRONG_SW_VERSION = -701 # wrong software version

# Client DLL version identifier
DLL_REQ_VER = 135                   # must match server’s expected DLL version


# Constants for module types
PLATINE_HW_IS_S8 = 1
PLATINE_HW_IS_I4O2 = 2
PLATINE_HW_IS_S4AD1 = 3
PLATINE_HW_IS_AR8_500 = 5
PLATINE_HW_IS_AJ1g = 7
PLATINE_HW_IS_I4J1 = 8
PLATINE_HW_IS_LICHT_S1 = 9
PLATINE_HW_IS_HS_TIME = 10
PLATINE_HW_IS_I4J2_SS = 11
PLATINE_HW_IS_I4O4_SS = 12
PLATINE_HW_IS_I2_PIR = 13
PLATINE_HW_IS_UP_RF_S4 = 14
PLATINE_HW_IS_IRRX = 15
PLATINE_HW_IS_AR_6_12_SS = 17
PLATINE_HW_IS_AJ_3_6_SS = 18
PLATINE_HW_IS_D4_AN = 20
PLATINE_HW_IS_LCD4x16 = 21
PLATINE_HW_IS_AJ4_500 = 22
PLATINE_HW_IS_S32A32 = 23
PLATINE_HW_IS_TLH = 25
PLATINE_HW_IS_LCD4x16M = 26
PLATINE_HW_IS_D4_AB = 27
PLATINE_HW_IS_ARING1 = 29
PLATINE_HW_IS_S1A1_WASSER_SUMMER = 30
PLATINE_HW_IS_S4 = 31
PLATINE_HW_IS_UP_GL = 32
PLATINE_HW_IS_POWER1 = 34
PLATINE_HW_IS_ALARM1 = 35
PLATINE_HW_IS_IR_TX_ALL = 36
PLATINE_HW_IS_PROUTE1 = 37
PLATINE_HW_IS_LED_2X7 = 38
PLATINE_HW_IS_EXT_LD = 39
PLATINE_HW_IS_AD3e = 40
PLATINE_HW_IS_AD3 = 41
PLATINE_HW_IS_AR6 = 42
PLATINE_HW_IS_AJ3 = 43
PLATINE_HW_IS_AT8 = 44
PLATINE_HW_IS_UP_RF = 45
PLATINE_HW_IS_AD110 = 46
PLATINE_HW_IS_UP_SI = 47
PLATINE_HW_IS_A32 = 48
PLATINE_HW_IS_VI4 = 49
PLATINE_HW_IS_HS_JAL = 50
PLATINE_HW_IS_VNC = 51
PLATINE_HW_IS_HS_STe8 = 52
PLATINE_HW_IS_HS_TCONTROL = 53
PLATINE_HW_IS_GSM = 54
PLATINE_HW_IS_LCD3 = 55
PLATINE_HW_IS_HS_CLIMATE = 56
PLATINE_HW_IS_HS_ACCESS = 57
PLATINE_HW_IS_19_AMP4 = 58
PLATINE_HW_IS_DALI = 59
PLATINE_HW_IS_EXT_AQV = 60
PLATINE_HW_IS_LCD320C = 61
PLATINE_HW_IS_ACCESS2_LCD = 62
PLATINE_HW_IS_BELL2 = 63
PLATINE_HW_IS_ACCESS2_MAIN = 64
PLATINE_HW_IS_VI_8X8 = 65
PLATINE_HW_IS_AU_4X4 = 66
PLATINE_HW_IS_HS_COUNTER = 67
PLATINE_HW_IS_HS_WL = 68
PLATINE_HW_IS_EXT_AQV_PW = 69
PLATINE_HW_IS_HS_SI6 = 70
PLATINE_HW_IS_S3 = 71
PLATINE_HW_IS_AR2 = 72
PLATINE_HW_IS_AT2E = 73
PLATINE_HW_IS_AJ1 = 74
PLATINE_HW_IS_EXT_CBE = 75
PLATINE_HW_IS_UP_BUZZER1 = 76
PLATINE_HW_IS_S4PLUS = 77
PLATINE_HW_IS_HSAnalog4 = 78
PLATINE_HW_IS_HS_WZ = 79
PLATINE_HW_IS_HFRXT = 80
PLATINE_HW_IS_HS_BARO = 81
PLATINE_HW_IS_EXT_CODESCHLOSS = 82
PLATINE_HW_IS_HFRX = 83
PLATINE_HW_IS_UP_T = 84
PLATINE_HW_IS_UP_RF2 = 85
PLATINE_HW_IS_HFRX_ELV868 = 86
PLATINE_HW_IS_IR_TX16 = 87
PLATINE_HW_IS_S32 = 88
PLATINE_HW_IS_PC_SOFTWARE = 100
PLATINE_HW_IS_VIRTUAL_BASE = 200

# --- Pakettypen (type8) ---
D0_SET_IP = 1
D0_ENUM_ALL = 2
D0_ACK_TYP = 3
D0_GET_TYP = 4
D0_ACK = 6
D0_NOACK = 7
D0_SET = 50
D0_INC = 51
D0_DEC = 52
D0_TOGGLE = 53
D0_REQ = 54
D0_ACTOR_ACK = 55
D0_SET_N = 59
D0_SENSOR_ACK = 65
D0_LOCK_STATE_ACK = 68
D0_VALUE_ACK = 101
D0_VALUE_REQ = 102
D0_STATUS_INFO = 105
D0_MODUL_BUSY = 35
D0_RD_ACTOR_DATA = 26
D0_RD_ACTOR_DATA_ACK = 31

D0_WR_SENSOR_DATA = 14
D0_RD_SENSOR_DATA = 15
D0_RD_SENSOR_DATA_ACK = 16

D0_GET_NAME_REQ = 33
D0_GET_NAME_ACK = 34

D0_MODUL_BUSY = 35

D0_RD_MODULSPEC_DATA = 37
D0_RD_MODULSPEC_DATA_ACK = 38
D0_WR_MODULSPEC_DATA = 39

D0_ENABLE_CONFIGURATION = 42
D1_ENABLE_CONFIGURATION_OK_BYTE = 0xD3
D1_ENABLE_FCONFIGURATION_OK_BYTE = 0xD7
D0_ENABLE_CONFIGURATION_OFF_BYTE = 0

D10_CONFIG_ENABLE_BIT = 0x01
D10_FCONFIG_ENABLE_BIT = 0x02

D0_SET_SERIAL = 44
D0_GET_SERIAL_REQ = 45
D0_GET_SERIAL_ACK = 46

D0_SET = 50
D0_INC = 51
D0_DEC = 52
D0_TOGGLE = 53
D0_REQ = 54
D0_ACTOR_ACK = 55
D0_START = 56
D0_STOP = 57
D0_SET_TIME_VAL = 58
D0_SET_N = 59
D0_DIM = 60
D0_START_DIM = 64

D0_SENSOR_ACK = 65
D0_LOCK = 66
D0_LOCK_STATE_REQ = 67
D0_LOCK_STATE_ACK = 68

D0_SAVE = 69
D0_RECALL = 70
D0_STOP_LOOP = 71
D0_MODUL_SPECIFIC_INFO = 72
D0_SEND_STORED = 73
D0_ERASE_GRP_DATA = 74

D0_SMS = 75
D1_SMS_TEXTBUF_INIT = 0x80
D1_SMS_PRIORITY_BIT1 = 0x40
D1_SMS_PRIORITY_BIT0 = 0x20
D1_SMS_PRIORITY_BITS = D1_SMS_PRIORITY_BIT0 + D1_SMS_PRIORITY_BIT1
D1_SEND_SMS_USE_TELBOOK = 1
D1_SEND_SMS_USE_NUMBER = 2
D1_SMS_ADD_TEXT = 3
D1_SMS_COPY_TEXT = 4
D1_SEND_SMS_USE_TELBOOK_MASK = 5

D0_SET_UP = 76
D0_SET_DOWN = 77
D0_STARTDIM_UP = 78
D0_STARTDIM_DOWN = 79

D0_VALUE_ACK = 101
D0_VALUE_REQ = 102
D0_VALUE_NOTREADY = 103

D0_STATUS_INFO = 105
D0_SAVE_CALIBRATION = 106
D0_SET_PROFIL = 107
D0_CHANGE_PROFIL = 108

D0_RD_EE16_DATA = 109
D0_RD_EE16_DATA_ACK = 110
D0_WR_EE16_DATA = 111

D0_TRANSFER = 112
D0_TRANSFER_CLEAR_TCS = 1
D0_TRANSFER_READ_TCS = 2

D0_TRANSFER_SELECT_MEM = 4
D0_TRANSFER_START_UPDATE = 5
D0_TRANSFER_SELECT_MEM_FLASH = 1
D0_TRANSFER_SELECT_MEM_EEPROM = 2

D0_TRANSFER_RD = 109
D0_TRANSFER_RESET = 110
D0_TRANSFER_BOOTLOADER = 111
D0_TRANSFER_CALC_CS = 112
D0_TRANSFER_WR = 115
D0_TRANSFER_ERASE = 116

D0_SLEEP = 114

# --- Bitmasken für type8 Flags ---
saCYCLIC = 0x04
saACK_REQ = 0x08
saPNR_MASK = 0xF0

# --- Status- und Steuerbits ---
D1_ENABLE_CONFIGURATION_OK_BYTE = 0xD3
D1_ENABLE_FCONFIGURATION_OK_BYTE = 0xD7

LOCK_BIT_AKTIV = 0x80
LOCK_BIT_BIN_VALUE = 1

# --- Spezialwerte ---
MI_EMPTY = 0
MI_BRC = 0xFFFF
BROADCASTIP = 0xFFFF

# --- SMS Flags ---
D0_SMS = 75
D1_SMS_TEXTBUF_INIT = 0x80
D1_SMS_PRIORITY_BIT1 = 0x40
D1_SMS_PRIORITY_BIT0 = 0x20
D1_SMS_PRIORITY_BITS = (D1_SMS_PRIORITY_BIT0 + D1_SMS_PRIORITY_BIT1)
D1_SEND_SMS_USE_TELBOOK = 1
D1_SEND_SMS_USE_TELBOOK_MASK = 5

IN_HW_NR_IS_CLOCK = 6

DCF77_SYNC_PHASE = 0x10
DCT_FEIERTAG = 8
DCF77_KEIN_EMPFANG = 4
DCF77_SOMMERZEIT = 1
DCF77_SOMMERZEIT_ANGUENDIGUNG = 2

VAL_IS_WORD16 = 14

IN_HW_NR_IS_TEMP = 9

IN_HW_NR_IS_PRESS_TENDENZ = 49

IN_HW_NR_IS_PRESS_MBAR = 48

IN_HW_NR_IS_LICHT_ANALOG = 5

IN_HW_NR_IS_KMH = 41

USE_FROMEL_16BIT_X8 = 7

VAL_IS_MENGE_LITER = 53

USE_FROMEL_16BIT_X10 = 8

IN_HW_NR_IS_REGEN = 47

IN_HW_NR_IS_HUMIDITY = 11

VAL_IS_MIN_TAG_WORD_SA = 50
VAL_IS_MIN_TAG_WORD_SU = 51

IN_HW_NR_IS_RF_TAG_READER = 7

OT_NO = 1
OT_DI = 2  # S4 Eingang
OT_AR = 3
OT_ART = 4
OT_AD = 5
OT_ADT = 6
OT_AX_TIME = 7
OT_AJ_MOT = 8
OT_AJ_PERC = 9
OT_MOTORRIEGEL_A = 10
OT_AD_MAX_PERC = 11
OT_ARS = 12  # AR als StatusInfo
OT_APWM = 13  # AT8e
OT_BLINK = 14
OT_FENSTERUE = 15
OT_LCD_A = 16
OT_PAKETROUTER_T1 = 17
OT_PAKETROUTER_T2 = 18
OT_PAKETROUTER_BASE = 19
OT_HS_TIME_TAB = 20
OT_HS_TIME_BASE = 21
OT_TLH_SOLLWERT = 22
OT_TLH_TAB = 23  # leerer Eintrag
OT_TLH_SENSOR_T = 24
OT_TLH_SENSOR_L = 25
OT_TLH_SENSOR_H = 26
OT_TLH_TAGWERT = 27
OT_TLH_NACHTWERT = 28
OT_TLH_TAB_ROUTING_ZIEL = 29
OT_TLH_TAB_T = 30
OT_TLH_TAB_L = 31
OT_TLH_TAB_H = 32

OT_HS_JAL_BASE = 33  # nur D0_SLEEP von WZ

OT_HS_JAL_BEREICH_REL_ZEIT_AUF = 35
OT_HS_JAL_BEREICH_REL_ZEIT_AB = 36
OT_HS_JAL_BEREICH_VOLL_AUF = 37  # Differenz 0.. für Voll nach Teilfahrt
OT_HS_JAL_BEREICH_VOLL_AB = 38  # Differenz 0.. für Voll nach Teilfahrt
OT_HS_JAL_BEREICH_TEILFAHRT_PERC = 39  # %-Wert Teilfahrt
OT_HS_JAL_BEREICH_TEILFAHRT_ENABLED = 40  # Teilfahrt 0 / 1

OT_HS_JAL_VIRTUAL_JAL_P = 41
OT_HS_JAL_VIRTUAL_JAL_M = 42

OT_HS_JAL_MAIN_TIME_NEXT = 43
OT_HS_JAL_MAIN_TIME_WOCHE = 44
OT_HS_JAL_MAIN_TIME_SA = 45
OT_HS_JAL_MAIN_TIME_SO = 46
OT_HS_JAL_MAIN_TIME_LICHTWERT = 47
OT_HS_JAL_MAIN_TIME_MODUS_AUF = 48
OT_HS_JAL_MAIN_TIME_MODUS_AB = 49

OT_HS_CLI_TIME_NEXT = 60
OT_HS_CLI_TIME_WOCHE = 61
OT_HS_CLI_TIME_SA = 62
OT_HS_CLI_TIME_SO = 63
OT_HS_CLI_BEREICH_T1 = 64
OT_HS_CLI_BEREICH_T2 = 65
OT_HS_CLI_BEREICH_T3 = 66
OT_HS_CLI_BEREICH_N = 67
OT_HS_CLI_BEREICH_P = 68
OT_HS_CLI_BEREICH_U = 69

OT_HS_CLI_BASE_3 = 75
OT_CLIMATE_RAUM = 76

OT_HS_CLI_BEREICH_REL_T1 = 80
OT_HS_CLI_BEREICH_REL_T2 = 81
OT_HS_CLI_BEREICH_REL_T3 = 82
OT_HS_CLI_BEREICH_REL_N = 83

OT_EXT_LD_BASE = 90
OT_EXT_LD_BASE_1 = 91
OT_EXT_LD_BASE_2 = 92

OT_SAFETY_BASE = 100
OT_SAFETY_EVENT = 101

OT_RF_DEST = 110

OT_GSM_BASE = 120

OT_ACCESS_LCD = 200
OT_ACCESS_KEY = 201
OT_ACCESS_OPTIONS = 202

OT_UP_RF_SRC = 210

OT_WAV_BELL = 220
OT_WAV_BELL_NOT = 221
OT_WAV_BELL_LCD = 222

OT_PIR2_BASE = 230
OT_PIR2_BASE_SABO = 231
OT_PIR2_BASE_DUNKEL = 232
OT_PIR2_BASE_HELL = 233
OT_PIR2_BASE_MODE = 234 
OT_AD_TOG_SOFT = 382

OUT_HW_NR_IS_ONOFF = 1
OUT_HW_NR_IS_JAL = 2
OUT_HW_NR_IS_DIMMER = 3
OUT_HW_NR_IS_TIMER = 4
OUT_HW_NR_IS_ONOFF_STATUS = 10
OUT_HW_NR_IS_SLOW_PWM = 12
OUT_HW_NR_IS_DALI_STATUS = 40
OUT_HW_NR_IS_BIN_BLINKER = 45
OUT_HW_NR_IS_FENSTERUEBERWACHUNG = 46
OUT_HW_NR_IS_SOFT_TOGGLE_DIM = 54
