; Control for overtemp.gcode: the same program with the thermistor staying cool must not halt.
; Without a heater target the firmware does not judge the reading, so M104 comes first. After the halt this move must be refused.
M104 S200
G1 X1 F3000
;@sim adc 3900   ; control: the thermistor stays at room temperature
;@sim wait 3000
M105
G1 X2
