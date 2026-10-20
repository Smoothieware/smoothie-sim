G21
G90
M106 S128
G1 X10 Y0 F3000
M104 S200
G1 X10 Y10
G1 X0 Y10 E1
M107
G1 X0 Y0
M105
G4 P10
G1 X5 Y5 Z1
M907 X0.8 Y0.8
M911
M119
G81 X10 Y10 Z-1 R1 F100
G80
M114
M115
M503
G30
T0
M406
M405
M119
G28
M3 S1000
M957
M5
M221 S50
G1 X1 Y1 S0.5 F1000
M906 X800
M909 X16
; ---- Robot: units, planes, arcs, work coordinate systems, state stack, feed/accel settings
G20
G1 X0.5 Y0.5 F100
G21
G17
G2 X10 Y0 I5 J0 F1200
G3 X0 Y0 I-5 J0
G18
G2 X5 Z1 I2.5 K0
G19
G3 Y5 Z0 J2.5 K0
G17
G91
G1 X1 Y1
G90
G92 X0 Y0 Z0
G92.1
G10 L2 P1 X1 Y1
G54
G10 L20 P2 X0 Y0
G55
G53 G1 X2 Y2
G54
M120
G1 X3 Y3
M121
M204 S2000
M205 X0.1
M203 X300 Y300
M220 S120
M221 S90
M200 D1.75
M92 X80 Y80
M114.1
M114.2
M114.3
M114.4
M82
M83
G1 E5 F300
G1 E-2 F300
G10
G11
M207 S2 F1200 Z0.1
M208 S0 F600
M400
M17
M84
M18
; ---- Player / SimpleShell / GcodeDispatch
M20
M21
M24
M25
M26
M27
M30
M110 N10
M115
M119
M114
M503
M500
M501
M504
mem
get temp
set_temp hotend 0
thermistors
calc_thermistor 100000
get pos
ls /sd
config-get sd temperature_control.hotend.p_factor
M305 S0
; ---- Extruder / TemperatureControl
M104 S0
M105
M109 S0
M301 S0 P10 I0.1 D100
M303 E0 S200 C2
M305 P0 S0
M306 
M570 S10
M143 S250
; ---- ZProbe / Endstops / calibration
G28.1
G28.2 X
G28.3 X0
G28.4 X
G28.5
G31
G32
M119
M666 X0 Y0 Z0
M665
M370
M371
M372
M373
M374 
M375
M376
M377
M378
M379
M380
M381
; ---- Switch / Laser / Spindle
M106 S255
M106 S0
M107
M3 S5000
M4 S5000
M5
M450
M451
M452
M453
G1 X5 Y5 S0.8 F600
M221 S100
; ---- Drilling cycles, filament detector, temperature switch, current, motor drivers
G81 X10 Y10 Z-1 R1 F100
G82 X10 Y10 Z-1 R1 P100 F100
G83 X10 Y10 Z-3 R1 Q1 F100
G80
M591 S1
M591
M906 X800 Y800
M907 X0.5 Y0.5
M909 X16
M910 X0
M911
M912
M913
M914
M915
M916
M917
M918
M919
; ---- emergency stop last: halts the machine, later lines would be refused
M112
M999
; ---- Stimulus: things G-code alone cannot do (";@sim" lines are read by the simulator, see sim/sim_main.cpp)
; Motor drivers: sub-codes, microstep change that rescales steps/mm, per-driver and raw register access, saved settings
M906 X900
M909.1 X32
M911
M911.1 P0
M911.1 X0 R0
M911.2 P0 R1 V5
M911.3 X0 S0 U4
M500
M503
; Temperature switch with an arm code: arm, disarm, heat past the threshold while armed, cool again
M1105 S1
M1105 S0
M1105 S1
;@sim adc 200
;@sim wait 3000
M1105 S0
;@sim adc 3900
;@sim wait 3000
; Filament detector: M404 settings, status, jam, bulge, retract, disable/enable, resume
M404 S1 P2 H1
M407
G91
G1 E10 F300
;@sim wait 2500
G1 E-2 F300
;@sim wait 2500
G1 E4 F300
;@sim wait 2500
G90
;@sim pulses 0.26 20
G1 E30 F300
;@sim wait 2500
M405
M407
M406
M407
resume
M601
;@sim pin 1.22 1
;@sim wait 2500
;@sim pin 1.22 0
; Panel: click the select button (debounced), plug in and remove the external SD card, show a message
;@sim pin 1.30 1
;@sim wait 300
;@sim pin 1.30 0
;@sim wait 300
;@sim pin 1.31 1
;@sim wait 300
;@sim pin 1.31 0
;@sim wait 300
;@sim pin 1.29 1
;@sim wait 2500
;@sim pin 1.29 0
;@sim wait 2500
M117 Hello
