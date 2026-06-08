# Telemetrie_identifier.py
ID_Pressure_High                    = 0x01
ID_Pressure_Low                     = 0x02
ID_Temperature_High                 = 0x03
ID_Temperature_Low                  = 0x04
###------------------------------------CAN_I------------------------------------####
# HV - Inverter

# Vehicle Control System


###------------------------------------CAN_II-----------------------------------####
# HV - Accumulator Management System

ID_TS_Voltage                       = 0x21
ID_TS_Current                       = 0x22
ID_TS_Currentdrawn                  = 0x23
ID_TS_AMS_Status                    = 0x24
ID_TS_Cell_Voltages_max             = 0x25
ID_TS_Cell_Voltages_min             = 0x26
ID_TS_Cell_Temprearure_max          = 0x27
ID_TS_Cell_Temprearure_min          = 0x28
ID_TS_Cellnumer_Voltages_max        = 0x29
ID_TS_Cellnumer_Voltages_min        = 0x2A
ID_TS_Cellnumer_Temprearure_max     = 0x2B
ID_TS_Cellnumer_Temprearure_min     = 0x2C

# Vehicle Control System
ID_TY_APPS_I                        = 0x30
ID_TY_APPS_II                       = 0x31
ID_LV_motor_control                 = 0x32
ID_LV_Pitot_pressure                = 0x33

# Sensor Hub Front
ID_TY_Brake_Pressure_front          = 0x41
ID_TY_Brake_Pressure_rear           = 0x42
ID_TY_Wheelspeed_FL                 = 0x43
ID_TY_Wheelspeed_FR                 = 0x44
ID_TY_Damper_Travel_FL              = 0x45
ID_TY_Damper_Travel_FR              = 0x46

# Sensor Hub Back
ID_TY_Wheelspeed_RL                 = 0x47
ID_TY_Wheelspeed_RR                 = 0x48
ID_TY_Colling_Temperature_RU        = 0x49
ID_TY_Colling_Temperature_RD        = 0x4A
ID_TY_Colling_Temperature_LU        = 0x4B
ID_TY_Colling_Temperature_LD        = 0x4C
ID_TY_Damper_Travel_RL              = 0x4D
ID_TY_Damper_Travel_RR              = 0x4E

# Driver Interface Controler 
ID_TS_Status                        = 0x50
ID_LV_R2D_Status                    = 0x51
#ID_SDC_Status                      = 0x52

# Fusebox
ID_LV_Voltage_Main                  = 0x60
ID_LV_NIMH_Voltage                  = 0x61
#ID_SDC_Status                      = 0x62     
ID_LV_Fuse_Readout                  = 0x63

# Steering Wheel Controler 
ID_SW_Encoder_left                  = 0x70
ID_SW_Encoder_right                 = 0x71
ID_SW_Push_Button_right             = 0x72
ID_SW_Push_Button_left              = 0x73
ID_SW_Lever_Switch_right            = 0x74
ID_SW_Lever_Switch_left             = 0x75

# Data Logger - AIM EVO V
ID_TY_Roll_Angle                    = 0x76
ID_TY_Pitch_Angle                   = 0x77
ID_TY_Yaw_Angle                     = 0x78
ID_TY_Acceleration_longitudinal     = 0x79
ID_TY_Acceleration_lateral          = 0x7A
ID_TY_Acceleration_vertical         = 0x7B
ID_TY_GPS_Speed                     = 0x7C
ID_TY_Best_Lap_Time                 = 0x7D
ID_TY_Predicted_Lap_Time            = 0x7E

# Micro Auto Box II

###------------------------------------CAN_EVO---------------------------------####
# Data Logger - AIM EVO V

# Micro Auto Box II

# Upright Acceleration Controler


# Tire Temperature Sensor





# Lookup table
ID_MAP = {
    1: {"name": "ID_Pressure_High",                       "group": "LV-System"},
    2: {"name": "ID_Pressure_Low",                        "group": "LV-System"},
    3: {"name": "ID_Temperature_High",                    "group": "LV-System"},
    4: {"name": "ID_Temperature_Low",                     "group": "LV-System"},

    # HV - Accumulator Management System
    33:  {"name": "ID_TS_Voltage",                        "group": "TSAC"},
    34:  {"name": "ID_TS_Current",                        "group": "TSAC"},
    35:  {"name": "ID_TS_Currentdrawn",                   "group": "TSAC"},
    36:  {"name": "ID_TS_AMS_Status",                     "group": "TSAC"},
    37:  {"name": "ID_TS_Cell_Voltages_max",              "group": "TSAC"},
    38:  {"name": "ID_TS_Cell_Voltages_min",              "group": "TSAC"},
    39:  {"name": "ID_TS_Cell_Temprearure_max",           "group": "TSAC"},
    40:  {"name": "ID_TS_Cell_Temprearure_min",           "group": "TSAC"},
    41:  {"name": "ID_TS_Cellnumer_Voltages_max",         "group": "TSAC"},
    42:  {"name": "ID_TS_Cellnumer_Voltages_min",         "group": "TSAC"},
    43:  {"name": "ID_TS_Cellnumer_Temprearure_max",      "group": "TSAC"},
    44:  {"name": "ID_TS_Cellnumer_Temprearure_min",      "group": "TSAC"},
    45:  {"name": "ID_LTC_Temperatur",                       "group": "LTC"},
    
    # Vehicle Control System
    48: {"name": "ID_TY_APPS_I",                          "group": "LV-System"},
    49: {"name": "ID_TY_APPS_II",                         "group": "LV-System"},
    50: {"name": "ID_LV_motor_control",                   "group": "LV-System"},
    51: {"name": "ID_LV_Pitot_pressure",                  "group": "LV-System"},
    
    # Sensor Hub Front
    65: {"name": "ID_TY_Brake_Pressure_front",            "group": "Suspension"},
    66: {"name": "ID_TY_Brake_Pressure_rear",             "group": "Suspension"},
    67: {"name": "ID_TY_Wheelspeed_FL",                   "group": "Suspension"},
    68: {"name": "ID_TY_Wheelspeed_FR",                   "group": "Suspension"},
    69: {"name": "ID_TY_Damper_Travel_FL",                "group": "Suspension"},
    70: {"name": "ID_TY_Damper_Travel_FR",                "group": "Suspension"},

    # Sensor Hub Back
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
    #x: {"name": "",               "group": "LV-System"},
}