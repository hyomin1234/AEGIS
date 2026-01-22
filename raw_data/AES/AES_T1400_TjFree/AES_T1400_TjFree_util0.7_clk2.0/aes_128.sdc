###################################################################

# Created by write_sdc on Tue Jan 20 02:58:29 2026

###################################################################
set sdc_version 1.9

set_units -time ps -resistance kOhm -capacitance fF -voltage V -current mA
set_max_fanout 20 [current_design]
create_clock [get_ports clk]  -period 2000  -waveform {0 1000}
set_propagated_clock [get_clocks clk]
