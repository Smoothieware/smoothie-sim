; Over-temperature halt through the real TemperatureControl: heat to a target, then the thermistor reads far above max_temp.
; Without a heater target the firmware does not judge the reading, so M104 comes first. After the halt this move must be refused.
M104 S200
G1 X1 F3000
;@sim adc 20
;@sim wait 3000
M105
G1 X2
