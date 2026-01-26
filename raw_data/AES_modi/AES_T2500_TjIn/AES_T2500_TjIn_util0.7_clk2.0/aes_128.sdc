###################################################################

# Created by write_sdc on Sat Jan 24 16:15:13 2026

###################################################################
set sdc_version 1.9

set_units -time ps -resistance kOhm -capacitance fF -voltage V -current mA
set_max_fanout 20 [current_design]
set_ideal_network [get_ports rst]
create_clock [get_ports clk]  -period 2000  -waveform {0 1000}
set_propagated_clock [get_clocks clk]
set_false_path   -from [get_ports rst]
