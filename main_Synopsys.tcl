date
source $::env(PRJ)/scripts/helper_Synopsys.tcl

if { [info exists vars(Design,cpuNo)] } {
	set_host_options -max_cores $vars(Design,cpuNo) 
}


if { $STAGE == "ndm" } {
	#### One-time tech-only library for ICC2. - tech ndm & macro ndm
	#### Technology file (.tf) and TLUplus file (.tlup) are required.
	prc_icc2_lm_setupConfig
	
	if {[info exists REVISION] && $REVISION == "MCellPre"} {
		set macro_ndm "macro_ndm_MCellPre"
	} elseif {[info exists REVISION] && $REVISION == "MCellPost"} {
		set macro_ndm "macro_ndm_MCellPost"
	} elseif {[info exists REVISION] && $REVISION == "Popt"} {
		set macro_ndm "macro_ndm_Popt"
	} else {
		set macro_ndm "macro_ndm"
	}
	
	if { ![file isdirectory $::env(techDir)/tech_ndm] || ![file isdirectory $::env(techDir)/$macro_ndm] } {
	# Set PVT condition
		set_pvt_configuration -clear_filter all -add -name $libName -process_numbers 1 -voltages $::env(techVol) -temperatures $::env(techTemp)
	} else {
		puts "\[SNUCAD\]: Both NDMs are already created, so skip this stage, or remove 'tech_ndm/' and/or '$macro_ndm/' in $::env(techDir) and rerun this stage."
		exit
	}
	
	########## Tech ndm ##########
	if { [file isdirectory $::env(techDir)/tech_ndm] } {
		sh rm -rf $::env(techDir)/tech_ndm
	}
	set_app_options -name lib.setting.use_tech_scale_factor -value true
	create_workspace -flow normal -technology $TFfiles tech_ndm 
#	puts "TECH LEF files: $techLEFfiles"
#	read_lef $techLEFfiles
	
	read_parasitic_tech -tlup $TLUPfiles

	#if { [llength $techLEFfiles] != 0 } {
	#	read_lef $techLEFfiles
	#}
	#
	#if {[file exists "config_tech_ndm.tcl"]} {	source config_tech_ndm.tcl }
	#if { [llength $techLEFfiles] != 0 } {
	#	report_workspace
	#	check_workspace -allow_missing
	#}
	commit_workspace -output $::env(techDir)/tech_ndm -force
	##############################
	
	########## Macro ndm ##########
	if { [file isdirectory $::env(techDir)/$macro_ndm] } {
		sh rm -rf $::env(techDir)/$macro_ndm
	}
	create_workspace -flow normal -technology $TFfiles $macro_ndm
	#create_workspace -flow normal -use_technology_lib tech_ndm $macro_ndm
	read_db $DBfiles
	read_lef $macroLEFfiles
	read_parasitic_tech -tlup $TLUPfiles
	
	if {[file exists "config_macro_ndm.tcl"]} {	source config_macro_ndm.tcl }
	report_workspace
	check_workspace -allow_missing
	commit_workspace -output $::env(techDir)/$macro_ndm -force
	##############################
}	\
else {
    source $::env(build_name).variables.tcl
	if { $TOOL == "DC" } {
		prc_setLinkTargetLibs
		set verilog_filelist	[ list ]
		set sverilog_filelist	[ list ]
		set vhd_filelist		[ list ]
		foreach fileName [glob -nocomplain -d $::env(RTLDir) *.vhd] {
		    set vhd_filelist [linsert $vhd_filelist end $fileName]
		}
		foreach fileName [glob -nocomplain -d $::env(RTLDir) *.v] {
		    if { [string match "*tb*" $fileName] || [string match "*test*" $fileName] } {
				echo "Info: Excluding testbench file $fileName"
				continue
			}
			set verilog_filelist [linsert $verilog_filelist end $fileName]
		}
		foreach fileName [glob -nocomplain -d $::env(RTLDir) *.sv] {
		    set sverilog_filelist [linsert $sverilog_filelist end $fileName]
		}
		if { [llength $verilog_filelist] == 0 && [llength $sverilog_filelist] == 0 && [llength $vhd_filelist] == 0} {
			puts "ERR> You should have at least 1 RTL file."
			exit
		}

		#MBFF
		#set hdlin_infer_multibit default_all
		#set_multibit_options -mode non_timing_driven


	
		sh rm -rf .WORK
		sh mkdir .WORK
		define_design_lib WORK -path .WORK
	
		set outDir ./data/01_syn_s
		sh mkdir -p $outDir
		
		# top module name
		set topModule $::env(build_name)
		if { [llength $verilog_filelist] != 0 } {
			analyze -f verilog -library WORK $verilog_filelist
		}
		if { [llength $sverilog_filelist] != 0 } {
			analyze -f sverilog -library WORK $sverilog_filelist
		}
		if { [llength $vhd_filelist] != 0 } {
			analyze -f vhdl -library WORK $vhd_filelist

		}
		
		elaborate $topModule
		current_design $topModule
		
		link
		
		write -f ddc -o $outDir/elab.ddc -hierarchy
		
		# constraints #
		set tunit [exec awk {/^set vars\(LibUnit,Time\)/{print $3}} $::env(build_name).variables.tcl]
		set tunit [string range $tunit 1 [string length $tunit]]
		
		if {[info exists env(clkName)]} {
			set CLK_PIN $::env(clkName)	
			echo "Clock source pin: $CLK_PIN"
		}
		if {[info exists vars(Syn,clkName)]} {
			set CLK_PIN $vars(Syn,clkName)
			echo "Clock source pin (from variables.tcl): $CLK_PIN"
		}
	
		if {[info exists env(rstName)]} {
			set RST_PIN $::env(rstName)
			echo "Reset pin: $RST_PIN"
		}
		if {[info exists vars(Syn,rstName)]} {
			set RST_PIN $vars(Syn,rstName)
			echo "Reset pin (from variables.tcl): $RST_PIN"
		}
		
		if {[info exists env(clkPeriod)]} {
			set CLK_TARGET $::env(clkPeriod)
			if {$tunit == "ps"} {
				set CLK_TARGET [ expr $CLK_TARGET * 1000 ]
			}
			echo "Clock target: $CLK_TARGET $tunit"
		}
		if {[info exists vars(Syn,clkPeriod)]} {
			set CLK_TARGET $vars(Syn,clkPeriod)
			if {$tunit == "ps"} {
				set CLK_TARGET [ expr $CLK_TARGET * 1000 ]
			}
			echo "Clock target (from variables.tcl): $CLK_TARGET $tunit"
		}
	
	
		if {[info exists vars(Syn,clkName)] || [info exists env(clkName)]} {
			if {[info exists vars(Syn,clkPeriod)] || [info exists env(clkPeriod)]} {
				create_clock -name "clk" -period $CLK_TARGET $CLK_PIN
			} else {
				echo "ERR: Clock target is not set"
				exit
			}
		}
	
		if {[info exists vars(Syn,rstName)] || [info exists env(rstName)] } {
			if {[sizeof_collection [get_ports -quiet ${RST_PIN}]] > 0} {
				set_dont_touch ${RST_PIN}
				set_ideal_network ${RST_PIN}
				set_false_path -from [get_ports ${RST_PIN}]
				echo "Info: Applied constraints to reset pin ${RST_PIN}"
			} else {
				echo "Warning: Reset pin ${RST_PIN} defined in variables but not found in design. Skipping reset constraints."
			}
		}
		

		
		set_max_fanout 20 [current_design]



		if { [file exists "constraints.tcl"] } {
			source constraints.tcl
		}
		################
		
		uniquify
		compile_ultra -no_autoungroup -no_boundary_optimization
		
		#if {$::env(flattenDesign) == 1} 
		if { [info exists vars(Syn,flatten)] && $vars(Syn,flatten) == 1} {
			ungroup -all -flatten
		}
		write -f ddc -o $outDir/compile.ddc -hierarchy
		
		current_design $topModule
		set reportDir $outDir/reports
		sh mkdir -p $reportDir
		report_qor > $reportDir/${topModule}_qor.rep 
		report_timing -significant_digits 6 > $reportDir/${topModule}_timing.rep 
		report_clock > $reportDir/${topModule}_clock.rep 
		report_power -significant_digits 6 > $reportDir/${topModule}_power.rep 
		report_area -hierarchy	> $reportDir/${topModule}_area.rep
		report_reference -hierarchy	> $reportDir/${topModule}_reference.rep
		report_path_group	> $reportDir/${topModule}_pathgroup.rep
		report_timing -capacitance -significant_digits 6
		
		#if {$::env(removeBus) == 1} 
		if { [info exists vars(Syn,removeBus) ] && $vars(Syn,removeBus) == 1} {
			define_name_rules verilog -allowed "A-Z a-z 0-9 _" -first_restricted "0-9 _" -remove_internal_net_bus -remove_port_bus -flatten_multi_dimension_busses -replacement_char "_" 
			change_names -rules verilog -hierarchy
		}
		set verilogout_no_tri true
		remove_ideal_network [all_clocks]
		set_propagated_clock [all_clocks]
		write_sdc -version 1.9 ${topModule}.sdc
		write -hierarchy -format verilog -output ${topModule}.netlist.v
	} \
	elseif { $TOOL == "ICC2" } {
		if { $STAGE == "floorplan" } {
			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			set outDir "data/02_pnr_s"
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig
			# Read verilog
			read_verilog $::env(build_name).netlist.v -top $::env(build_name)
			link_block
			
			#prc_icc2_mmmcConfig
			
			# Initialize floorplan
			set offset [list $vars(FloorPlan,LeftMargin) $vars(FloorPlan,BottomMargin) $vars(FloorPlan,RightMargin) $vars(FloorPlan,TopMargin)]
			if { $vars(FloorPlan,Type) == "r" } {
				initialize_floorplan -core_offset $offset -core_utilization $vars(FloorPlan,var2) -side_ratio [list 1 $vars(FloorPlan,var1)]
			} elseif { $vars(FloorPlan,Type) == "d" } {
				initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type die
			} elseif { $vars(FloorPlan,Type) == "s" } {
				initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type core
			}
			
			prc_icc2_setPNRmodes
			if { [ file exists "config.tcl" ] } { source config.tcl }
			puts "****************************************************************************************************"
			puts ""
			puts "\[SNUCAD\]: specify the floorplan"
			puts ""
			puts "		 > man initialize_floorplan" 
			puts ""
			puts "\[SNUCAD\]: if the design has no hard macros, this step is not required. So just exit:"
			puts ""
			puts "		 > exit"
			puts ""
			puts "\[SNUCAD\]: if the design has hard macros,"
			puts "\[SNUCAD\]: Place the hardmacros and save the floorplan:"
			puts ""
			puts "		> save_block -as 00_Floorplan"
			puts "		> exit"
			puts ""
			puts "****************************************************************************************************"
			
		}	\
		elseif { $STAGE == "floorplan_initial" } {
			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			set outDir "data/02_pnr_s"
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig
			# Read verilog
			read_verilog $::env(build_name).netlist.v -top $::env(build_name)
			link_block
			
			#prc_icc2_mmmcConfig
			
			# Initialize floorplan
			set offset [list $vars(FloorPlan,LeftMargin) $vars(FloorPlan,BottomMargin) $vars(FloorPlan,RightMargin) $vars(FloorPlan,TopMargin)]
			if { $vars(FloorPlan,Type) == "r" } {
				initialize_floorplan -core_offset $offset -core_utilization $vars(FloorPlan,var2) -side_ratio [list 1 $vars(FloorPlan,var1)]
			} elseif { $vars(FloorPlan,Type) == "d" } {
				initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type die
			} elseif { $vars(FloorPlan,Type) == "s" } {
				initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type core
			}
			
			prc_icc2_setPNRmodes
			write_def $::env(build_name).floorplan_initial.def

			
		}	\
		elseif { $STAGE == "floorplan_post" } {
			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			set outDir "data/02_pnr_s"
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig
			# Read verilog
			read_verilog $::env(build_name).netlist.v -top $::env(build_name)
			link_block
			
			#prc_icc2_mmmcConfig
			
			read_def $::env(build_name).floorplan.def
			prc_icc2_setPNRmodes
			save_block -as 00_Floorplan

			
		}	\
		elseif { $STAGE == "pnr_no_opt" } {
			
			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			if {[info exists REVISION] && $REVISION == "MCellPre"} {
				set outDir "data/02_pnr_MCellPre_s"
			} elseif {[info exists REVISION] && $REVISION == "MCellPost"} {
				set outDir "data/02_pnr_MCellPost_s"
			} elseif {[info exists REVISION] && $REVISION == "Popt"} {
				set outDir "data/02_pnr_Popt_s"
			} else {
				set outDir "data/02_pnr_s"
			}
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig
			
			if { [ file exists $outDir/final/design.ndm ] } {
				open_block final
				if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
			} else {	
				if { [ file exists $outDir/04_Route/design.ndm ] } {
					open_block 04_Route
					if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
				} else {
					if { [ file exists $outDir/03_Clock_opt/design.ndm ] } {
						open_block 03_Clock_opt
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} elseif { [ file exists $outDir/03_Clock_noOpt/design.ndm ] } {
						open_block 03_Clock_noOpt
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} else {
						if { [ file exists $outDir/02_Place_opt/design.ndm ] } {
							open_block 02_Place_opt
							if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
						} else {
							if { [ file exists $outDir/01_Placement/design.ndm ] } {
								open_block 01_Placement
								if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
							} else {
								if { [ file exists $outDir/00_Place_coarse/design.ndm ] } {
									open_block 00_Place_coarse
									if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
								} else {
									if { [ file exists $outDir/00_Floorplan/design.ndm ] } {
										open_block 00_Floorplan
										if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
									} else {
										# Read verilog
										if {[info exists REVISION] && $REVISION == "MCellPost"} {
											read_verilog $::env(build_name).place_opt.v -top $::env(build_name)
										} elseif {[info exists REVISION] && $REVISION == "Popt"} {
											read_verilog $::env(build_name).graphH.netlist.v -top $::env(build_name)
										} else {
											read_verilog $::env(build_name).netlist.v -top $::env(build_name)
										}
										
										# Read DEF or create floorplan
										if {[info exists REVISION] && $REVISION == "MCellPost"} {
											read_def $::env(build_name).place_opt.def
										} elseif { [ file exists "floorplan.def" ] } { 
											read_def floorplan.def 
										} else {	
											# Initialize floorplan
											if {[info exists REVISION] && $REVISION == "MCellPre"} {
												source MCell_data/$::env(build_name).preMerge.icc2.tcl
											}
											set offset [list $vars(FloorPlan,LeftMargin) $vars(FloorPlan,BottomMargin) $vars(FloorPlan,RightMargin) $vars(FloorPlan,TopMargin)]
											set_attribute [get_layers {M1 MINT2 MINT4 MSMG1 MSMG3 MSMG5 MG2}] routing_direction vertical
											set_attribute [get_layers {MINT1 MINT3 MINT5 MSMG2 MSMG4 MG1}] routing_direction horizontal
											if { $vars(FloorPlan,Type) == "r" } {
												initialize_floorplan -core_offset $offset -core_utilization $vars(FloorPlan,var2) -side_ratio [list 1 $vars(FloorPlan,var1)]
											} elseif { $vars(FloorPlan,Type) == "d" } {
												initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type die
											} elseif { $vars(FloorPlan,Type) == "s" } {
												initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type core
											}
										}
										#prc_icc2_mmmcConfig
										prc_icc2_setPNRmodes
										if { [ file exists "config.tcl" ] } { source config.tcl }
										
										if {[info exists REVISION] && $REVISION == "MCellPost"} {
										} else {
											save_block -as 00_Floorplan
										}
									}							
									if {[info exists REVISION] && $REVISION == "MCellPost"} {
									} else {
										# Corase placement
										#create_placement -floorplan
										set_app_options -name place.fix_hard_macros -value true
										create_placement 
									
										# Pin placement
										place_pins -self
										#save_block -as $outDir/00_Place_coarse
										save_block -as 00_Place_coarse
									}
								}						
								## Placement
								set_app_options -name opt.common.user_instance_name_prefix -value "placeOpt_"
								legalize_placement
								save_block -as 01_Placement

							}
						}
					}	
					## Routing
					set_app_options -name opt.common.user_instance_name_prefix -value "routeOpt_"
					if { [ file exists "config_pre_route.tcl" ] } { source config_pre_route.tcl }
					route_auto -max_detail_route_iterations $vars(PNR,routingIteration)
					if { [ file exists "config_post_route.tcl" ] } { source config_post_route.tcl }
					#save_block -as $outDir/04_Route
					save_block -as 04_Route
				}	
				
				save_block -as final
			}
			## Wrap-up
			if { [ file exists "config_pre_wrapup.tcl" ] } { source config_pre_wrapup.tcl }
			update_timing
			report_clock_qor -all > $outDir/$::env(build_name).clock_qor.icc2
			report_timing -nets -significant_digits	6  > $outDir/$::env(build_name).timing.icc2
			report_power -significant_digits 6 > $outDir/$::env(build_name).power.icc2
			report_power -cell_power  -significant_digits 6 >  $outDir/$::env(build_name).cellPower.icc2
			report_power -net_power  -significant_digits 6 >  $outDir/$::env(build_name).netPower.icc2
	
			if {[info exists REVISION]} {
				sh mkdir -p SPEF/$REVISION
				write_parasitics -compress -output SPEF/$REVISION/$::env(build_name).final
				write_verilog $::env(build_name)_$REVISION.final.v
				write_def -version 5.7 $::env(build_name)_$REVISION.final.def
				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name).summary.rpt
			} else {
				sh mkdir -p SPEF
				write_parasitics -compress -output SPEF/$::env(build_name).final
				write_verilog $::env(build_name).final.v
				write_def -version 5.7 $::env(build_name).final.def
				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name).summary.rpt
			}
			
			#get_drc_error_data -all
			#open_drc_error_data zroute.err
			#set err_data zroute.err
			#set type [get_drc_error_types -error_data $err_data {*}]
			#report_drc_errors -error_data $err_data -error_type $type -layers {*} -report_type detailed  > DRVs.log


		}	\
		elseif { $STAGE == "pnr_fp" } {
			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			
			set outDir "data/02_pnr_s_$::env(IDX)"
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig
			
			if { [ file exists $outDir/final/design.ndm ] } {
				open_block final
				if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
			} else {	
				if { [ file exists $outDir/04_Route/design.ndm ] } {
					open_block 04_Route
					if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
				} else {
					if { [ file exists $outDir/03_Clock_opt/design.ndm ] } {
						open_block 03_Clock_opt
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} elseif { [ file exists $outDir/03_Clock_noOpt/design.ndm ] } {
						open_block 03_Clock_noOpt
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} else {
						if { [ file exists $outDir/02_Place_opt/design.ndm ] } {
							open_block 02_Place_opt
							if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
						} else {
							if { [ file exists $outDir/01_Placement/design.ndm ] } {
								open_block 01_Placement
								if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
							} else {
								if { [ file exists $outDir/00_Place_coarse/design.ndm ] } {
									open_block 00_Place_coarse
									if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
								} else {
									if { [ file exists $outDir/00_Floorplan/design.ndm ] } {
										open_block 00_Floorplan
										if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
									} else {
										# Read verilog

										read_verilog $::env(build_name).netlist.v -top $::env(build_name)
										set_attribute [get_layers {M1 MINT2 MINT4 MSMG1 MSMG3 MSMG5 MG2}] routing_direction vertical
										set_attribute [get_layers {MINT1 MINT3 MINT5 MSMG2 MSMG4 MG1}] routing_direction horizontal
										read_def $::env(build_name).floorplan_$::env(IDX).def 
										
										prc_icc2_mmmcConfig
										prc_icc2_setPNRmodes
										save_block -as 00_Floorplan
										
									}							
									set_app_options -name place.fix_hard_macros -value true
									create_placement 
									# Pin placement
									place_pins -self
									save_block -as 00_Place_coarse
								}						
								## Placement
								set_app_options -name opt.common.user_instance_name_prefix -value "placeOpt_"
								if {[info exists REVISION] && $REVISION == "MCellPost"} {
								} else {
									if { [ file exists "config_pre_placement.tcl" ] } { source config_pre_placement.tcl }
									if {[info exists REVISION] && $REVISION == "placeOnly"} {
										place_opt -to initial_place
										if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
										save_block -as 01_Placement
										write_def -version 5.7 $::env(build_name).placeOnly.def
										exit
									} elseif { [ info exists vars(PNR,place_opt_design) ] && $vars(PNR,place_opt_design) == 0 } {
										place_opt -to final_place
										if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
										save_block -as 01_Placement
									} else {
									}
								}
								write_def $::env(build_name)_$::env(IDX).place.def
							}
							## pre-CTS opt
							if {[info exists REVISION] && $REVISION == "MCellPost"} {
								source MCell_data/$::env(build_name).postMerge.icc2.tcl
								if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
								save_block -as 02_Place_opt_merged
							} else {
								if { [ info exists vars(PNR,place_opt_design) ] && $vars(PNR,place_opt_design) == 0 } {
								} else {
									place_opt
									if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
									save_block -as 02_Place_opt
								}
							}
						}				
						## CTS
						set_app_options -name opt.common.user_instance_name_prefix -value "clockOpt_"
						#clock_opt -to route_clock
						if { [ file exists "config_pre_clock_opt.tcl" ] } { source config_pre_clock_opt.tcl }
						
						if {[info exists vars(PNR,clock_opt_design)] && $vars(PNR,clock_opt_design) == 0} {
							clock_opt -to route_clock
						} else {
							clock_opt
						}
						
						if { [ file exists "config_post_clock_opt.tcl" ] } { source config_post_clock_opt.tcl }
						#save_block -as $outDir/03_Clock_opt
						
						if {[info exists vars(PNR,clock_opt_design)] && $vars(PNR,clock_opt_design) == 0} {
							save_block -as 03_Clock_noOpt
						} else {
							save_block -as 03_Clock_opt
						}
					}	
					## Routing
					set_app_options -name opt.common.user_instance_name_prefix -value "routeOpt_"
					if { [ file exists "config_pre_route.tcl" ] } { source config_pre_route.tcl }
					route_auto -max_detail_route_iterations $vars(PNR,routingIteration)
					if { [ file exists "config_post_route.tcl" ] } { source config_post_route.tcl }
					#save_block -as $outDir/04_Route
					save_block -as 04_Route
				}	
				## Post-route opt. (run route_opt again)
				if { [ file exists "config_pre_postRouteOpt.tcl" ] } { source config_pre_postRouteOpt.tcl }
	
				if {[info exists vars(PNR,route_opt_design)] && $vars(PNR,route_opt_design) == 0} {
				} else {
					#compute_clock_latency -verbose
					route_opt
					route_opt
				}
				
				if { [ file exists "config_post_postRouteOpt.tcl" ] } { source config_post_postRouteOpt.tcl }
				#save_block -as $outDir/final
				save_block -as final
			}


			if { ![ file exists $outDir/$::env(build_name)_$::env(IDX).netPower.icc2 ] } {
				## Wrap-up
				if { [ file exists "config_pre_wrapup.tcl" ] } { source config_pre_wrapup.tcl }
				update_timing
				report_clock_qor -all > $outDir/$::env(build_name)_$::env(IDX).clock_qor.icc2
				report_timing -nets -significant_digits	6  > $outDir/$::env(build_name)_$::env(IDX).timing.icc2
				report_power -significant_digits 6 > $outDir/$::env(build_name)_$::env(IDX).power.icc2
				report_power -cell_power  -significant_digits 6 >  $outDir/$::env(build_name)_$::env(IDX).cellPower.icc2
				report_power -net_power  -significant_digits 6 >  $outDir/$::env(build_name)_$::env(IDX).netPower.icc2
			}
	
			if { ![ file exists $::env(build_name)_$::env(IDX).final.def ] } {
				if {[info exists REVISION]} {
					sh mkdir -p SPEF/$REVISION
					write_parasitics -compress -output SPEF/$REVISION/$::env(build_name)_$::env(IDX).final
					write_verilog $::env(build_name)_$::env(IDX)_$REVISION.final.v
					write_def $::env(build_name)_$::env(IDX)_$REVISION.final.def
					report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name)_$::env(IDX).summary.rpt
				} else {
					sh mkdir -p SPEF
					write_parasitics -compress -output SPEF/$::env(build_name)_$::env(IDX).final
					write_verilog $::env(build_name)_$::env(IDX).final.v
					write_def $::env(build_name)_$::env(IDX).final.def
					report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name)_$::env(IDX).summary.rpt
				}
			}
			if { ![ file exists $::env(build_name)_$::env(IDX)_DRVs.log ] } {
				close_blocks -force
				open_block final

				start_gui
				get_drc_error_data -all
				open_drc_error_data zroute.err
				gui_show_error_data zroute.err
				gui_report_errors -file $::env(build_name)_$::env(IDX)_DRVs.log
			}
		}	\
		elseif { $STAGE == "pnr" } {
			
			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			if {[info exists REVISION] && $REVISION == "MCellPre"} {
				set outDir "data/02_pnr_MCellPre_s"
			} elseif {[info exists REVISION] && $REVISION == "MCellPost"} {
				set outDir "data/02_pnr_MCellPost_s"
			} elseif {[info exists REVISION] && $REVISION == "Popt"} {
				set outDir "data/02_pnr_Popt_s"
			} else {
				set outDir "data/02_pnr_s"
			}
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig
			
			if { [ file exists $outDir/final/design.ndm ] } {
				open_block final
				if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
			} else {	
				if { [ file exists $outDir/04_Route/design.ndm ] } {
					open_block 04_Route
					if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
				} else {
					if { [ file exists $outDir/03_Clock_opt/design.ndm ] } {
						open_block 03_Clock_opt
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} elseif { [ file exists $outDir/03_Clock_noOpt/design.ndm ] } {
						open_block 03_Clock_noOpt
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} else {
						if { [ file exists $outDir/02_Place_opt/design.ndm ] } {
							open_block 02_Place_opt
							if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
						} else {
							if { [ file exists $outDir/01_Placement/design.ndm ] } {
								open_block 01_Placement
								if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
							} else {
								if { [ file exists $outDir/00_Place_coarse/design.ndm ] } {
									open_block 00_Place_coarse
									if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
								} else {
									if { [ file exists $outDir/00_Floorplan/design.ndm ] } {
										open_block 00_Floorplan
										if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
									} else {
										# Read verilog
										if {[info exists REVISION] && $REVISION == "MCellPost"} {
											read_verilog $::env(build_name).place_opt.v -top $::env(build_name)
										} elseif {[info exists REVISION] && $REVISION == "Popt"} {
											read_verilog $::env(build_name).graphH.netlist.v -top $::env(build_name)
										} else {
											read_verilog $::env(build_name).netlist.v -top $::env(build_name)
										}
										
										# Read DEF or create floorplan
										if {[info exists REVISION] && $REVISION == "MCellPost"} {
											read_def $::env(build_name).place_opt.def
										} elseif { [ file exists "floorplan.def" ] } { 
											read_def floorplan.def 
										} else {	
											# Initialize floorplan
											if {[info exists REVISION] && $REVISION == "MCellPre"} {
												source MCell_data/$::env(build_name).preMerge.icc2.tcl
											}
											set offset [list $vars(FloorPlan,LeftMargin) $vars(FloorPlan,BottomMargin) $vars(FloorPlan,RightMargin) $vars(FloorPlan,TopMargin)]
                                            set_attribute [get_layers {M1 MINT2 MINT4 MSMG1 MSMG3 MSMG5 MG2}] routing_direction vertical
                                            set_attribute [get_layers {MINT1 MINT3 MINT5 MSMG2 MSMG4 MG1}] routing_direction horizontal
											if { $vars(FloorPlan,Type) == "r" } {
												initialize_floorplan -core_offset $offset -core_utilization $vars(FloorPlan,var2) -side_ratio [list 1 $vars(FloorPlan,var1)]
											} elseif { $vars(FloorPlan,Type) == "d" } {
												initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type die
											} elseif { $vars(FloorPlan,Type) == "s" } {
												initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type core
											}
										}
										prc_icc2_mmmcConfig
										prc_icc2_setPNRmodes
										if { [ file exists "config.tcl" ] } { source config.tcl }
										
										if {[info exists REVISION] && $REVISION == "MCellPost"} {
										} else {
											save_block -as 00_Floorplan
										}
									}							
									if {[info exists REVISION] && $REVISION == "MCellPost"} {
									} else {
										# Corase placement
										#create_placement -floorplan
										set_app_options -name place.fix_hard_macros -value true
										create_placement 
									
										# Pin placement
										place_pins -self
										#save_block -as $outDir/00_Place_coarse
										save_block -as 00_Place_coarse
									}
								}						
								## Placement
								set_app_options -name opt.common.user_instance_name_prefix -value "placeOpt_"
								if {[info exists REVISION] && $REVISION == "MCellPost"} {
								} else {
									if { [ file exists "config_pre_placement.tcl" ] } { source config_pre_placement.tcl }
									if {[info exists REVISION] && $REVISION == "placeOnly"} {
										place_opt -to initial_place
										if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
										save_block -as 01_Placement
										write_def -version 5.7 $::env(build_name).placeOnly.def
										exit
									} elseif { [ info exists vars(PNR,place_opt_design) ] && $vars(PNR,place_opt_design) == 0 } {
										place_opt -to final_place
										if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
										save_block -as 01_Placement
									} else {
									}
								}
                                write_def $::env(build_name).place.def
							}
							## pre-CTS opt
							if {[info exists REVISION] && $REVISION == "MCellPost"} {
								source MCell_data/$::env(build_name).postMerge.icc2.tcl
								if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
								save_block -as 02_Place_opt_merged
							} else {
								if { [ info exists vars(PNR,place_opt_design) ] && $vars(PNR,place_opt_design) == 0 } {
								} else {
									place_opt
									if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
									save_block -as 02_Place_opt
								}
							}
						}				
						## CTS
						set_app_options -name opt.common.user_instance_name_prefix -value "clockOpt_"
						#clock_opt -to route_clock
						if { [ file exists "config_pre_clock_opt.tcl" ] } { source config_pre_clock_opt.tcl }
						
						if {[info exists vars(PNR,clock_opt_design)] && $vars(PNR,clock_opt_design) == 0} {
							clock_opt -to route_clock
						} else {
							clock_opt
						}
						if { [ file exists "config_post_clock_opt.tcl" ] } { source config_post_clock_opt.tcl }
						#save_block -as $outDir/03_Clock_opt
						
						if {[info exists vars(PNR,clock_opt_design)] && $vars(PNR,clock_opt_design) == 0} {
							save_block -as 03_Clock_noOpt
						} else {
							save_block -as 03_Clock_opt
						}
					}	
					## Routing
					set_app_options -name opt.common.user_instance_name_prefix -value "routeOpt_"
					if { [ file exists "config_pre_route.tcl" ] } { source config_pre_route.tcl }
					route_auto -max_detail_route_iterations $vars(PNR,routingIteration)
					if { [ file exists "config_post_route.tcl" ] } { source config_post_route.tcl }
					#save_block -as $outDir/04_Route
					save_block -as 04_Route
				}	
				## Post-route opt. (run route_opt again)
				if { [ file exists "config_pre_postRouteOpt.tcl" ] } { source config_pre_postRouteOpt.tcl }
	
				if {[info exists vars(PNR,route_opt_design)] && $vars(PNR,route_opt_design) == 0} {
				} else {
					#compute_clock_latency -verbose
					route_opt
					route_opt
				}
				
				if { [ file exists "config_post_postRouteOpt.tcl" ] } { source config_post_postRouteOpt.tcl }
				#save_block -as $outDir/final
				save_block -as final
			}
			## Wrap-up
			if { [ file exists "config_pre_wrapup.tcl" ] } { source config_pre_wrapup.tcl }
			update_timing
			report_clock_qor -all > $outDir/$::env(build_name).clock_qor.icc2
			report_timing -nets -significant_digits	6  > $outDir/$::env(build_name).timing.icc2
			report_power -significant_digits 6 > $outDir/$::env(build_name).power.icc2
			report_power -cell_power  -significant_digits 6 >  $outDir/$::env(build_name).cellPower.icc2
			report_power -net_power  -significant_digits 6 >  $outDir/$::env(build_name).netPower.icc2
	
			if {[info exists REVISION]} {
				sh mkdir -p SPEF/$REVISION
				write_parasitics -compress -output SPEF/$REVISION/$::env(build_name).final
				write_verilog $::env(build_name)_$REVISION.final.v
				write_def -version 5.7 $::env(build_name)_$REVISION.final.def
				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name).summary.rpt
			} else {
				sh mkdir -p SPEF
				write_parasitics -compress -output SPEF/$::env(build_name).final
				write_verilog $::env(build_name).final.v
				write_def -version 5.7 $::env(build_name).final.def
				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name).summary.rpt
			}
			
			get_drc_error_data -all
			open_drc_error_data zroute.err
			set err_data zroute.err
			set type [get_drc_error_types -error_data $err_data {*}]
            #report_drc_errors -error_data $err_data -error_type $type -layers {*} -report_type detailed  >> DRVs.log

            start_gui
            get_drc_error_data -all
            open_drc_error_data zroute.err
            gui_show_error_data zroute.err
            gui_report_errors -file DRVs_summary.log


		} elseif { $STAGE == "pnr_cost" } {
			if { ![ file exists $::env(build_name).sdc ] } {
					puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
				}
				if { ![ file exists $::env(build_name).netlist.v ] } {
					puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
				}
				if { ![ file exists $::env(build_name).variables.tcl ] } {
					puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
				}
			
				set outDir "data/02_pnr_s_$::env(COST)"
				
				prc_icc2_setupConfig
				
				if { [ file exists $outDir/final/design.ndm ] } {
					open_block final
					if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
				} else {	
					if { [ file exists $outDir/04_Route/design.ndm ] } {
						open_block 04_Route
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} else {
						if { [ file exists $outDir/03_Clock_opt/design.ndm ] } {
							open_block 03_Clock_opt
							if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
						} else {
							if { [ file exists $outDir/02_Place_opt/design.ndm ] } {
								open_block 02_Place_opt
								# Initialize floorplan
								read_def $::env(COST_DEF)

								save_block
								#save_block -as 02_Place_opt
							}
							## CTS
							prc_icc2_setPNRmodes
							#clock_opt -to route_clock
							if { [ file exists "config_pre_clock_opt.tcl" ] } { source config_pre_clock_opt.tcl }
							clock_opt
							if { [ file exists "config_post_clock_opt.tcl" ] } { source config_post_clock_opt.tcl }
							#save_block -as $outDir/03_Clock_opt
							save_block -as 03_Clock_opt
						}	
						## Routing
						prc_icc2_setPNRmodes
						if { [ file exists "config_pre_route.tcl" ] } { source config_pre_route.tcl }
						set_attribute -objects [get_layers {M1 MINT2 MINT4}] -name routing_direction -value vertical
						set_attribute -objects [get_layers {MINT1 MINT3 MINT5}] -name routing_direction -value horizontal

						#route_global		
						#write_def gr.def
						#route_track
						#route_detail -max_number_iterations $vars(PNR,routingIteration)
						route_auto -max_detail_route_iterations $vars(PNR,routingIteration)
						if { [ file exists "config_post_route.tcl" ] } { source config_post_route.tcl }
						#save_block -as $outDir/04_Route
						save_block -as 04_Route
					}	
					
					# Post-route opt. (run route_opt again)
					if { [ file exists "config_pre_postRouteOpt.tcl" ] } { source config_pre_postRouteOpt.tcl }
					compute_clock_latency -verbose
					route_opt
					route_opt
					if { [ file exists "config_post_postrouteOPT.tcl" ] } { source config_post_postRouteOpt.tcl }
					#save_block -as $outDir/final
					save_block -as final
				}
				## Wrap-up
				if { [ file exists "config_pre_wrapup.tcl" ] } { source config_pre_wrapup.tcl }
				update_timing
				report_timing -nets > $outDir/$::env(build_name)_$::env(COST).timing.icc2
				report_power > $outDir/$::env(build_name)_$::env(COST).power.icc2
				report_power -cell_power >  $outDir/$::env(build_name)_$::env(COST).cellPower.icc2
				report_power -net_power >  $outDir/$::env(build_name)_$::env(COST).netPower.icc2

				sh mkdir -p SPEF
				write_parasitics -compress -output SPEF/$::env(build_name)_$::env(COST).final
				write_verilog $::env(build_name)_$::env(COST).final.v
				write_def -version 5.7 $::env(build_name)_$::env(COST).final.def
				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name)_$::env(COST).summary.rpt
				
				get_drc_error_data -all
				open_drc_error_data zroute.err
				set err_data zroute.err
				set type [get_drc_error_types -error_data $err_data {*}]
				report_drc_errors -error_data $err_data -error_type $type -layers {*} -report_type detailed  > DRVs_$::env(COST).log

				date

		} elseif { $STAGE == "pnr_cost_no_opt" } {

			if { ![ file exists $::env(build_name).sdc ] } {
					puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
				}
				if { ![ file exists $::env(build_name).netlist.v ] } {
					puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
				}
				if { ![ file exists $::env(build_name).variables.tcl ] } {
					puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
				}
			
				set outDir "data/02_pnr_s_no_opt_$::env(COST)"
				
				prc_icc2_setupConfig
                #set_ref_libs -ref_libs {/home/users/suwankim/CAD_choi/tech/nangate15_clean_phc/macro_ndm /home/users/suwankim/CAD_choi/tech/nangate15_clean_phc/tech_ndm} -use_technology_lib /home/users/suwankim/CAD_choi/tech/nangate15_clean_phc/tech_ndm
				

					if { [ file exists $outDir/04_Route/design.ndm ] } {
						open_block 04_Route
						if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
					} else {
						if { [ file exists $outDir/02_Place_opt/design.ndm ] } {
								open_block 02_Place_opt
								# Initialize floorplan
								read_def $::env(COST_DEF)
							
								legalize_placement
								save_block
								#save_block -as 02_Place_opt
						}
						
						## Routing
						prc_icc2_setPNRmodes
						if { [ file exists "config_pre_route.tcl" ] } { source config_pre_route.tcl }
						set_attribute -objects [get_layers {M1 MINT2 MINT4}] -name routing_direction -value vertical
						set_attribute -objects [get_layers {MINT1 MINT3 MINT5}] -name routing_direction -value horizontal

						#route_global		
						#write_def gr.def
						#route_track
						#route_detail -max_number_iterations $vars(PNR,routingIteration)
						route_auto -max_detail_route_iterations $vars(PNR,routingIteration)
						if { [ file exists "config_post_route.tcl" ] } { source config_post_route.tcl }
						#save_block -as $outDir/04_Route
						save_block -as 04_Route
					}	
					
				
				## Wrap-up
				if { [ file exists "config_pre_wrapup.tcl" ] } { source config_pre_wrapup.tcl }
				update_timing
				report_timing -nets > $outDir/$::env(build_name)_no_opt_$::env(COST).timing.icc2
				report_power > $outDir/$::env(build_name)_no_opt_$::env(COST).power.icc2
				report_power -cell_power >  $outDir/$::env(build_name)_no_opt_$::env(COST).cellPower.icc2
				report_power -net_power >  $outDir/$::env(build_name)_no_opt_$::env(COST).netPower.icc2

				sh mkdir -p SPEF
				write_parasitics -compress -output SPEF/$::env(build_name)_no_opt_$::env(COST).final
				write_verilog $::env(build_name)_no_opt_$::env(COST).final.v
				write_def -version 5.7 $::env(build_name)_no_opt_$::env(COST).final.def
				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name)_no_opt_$::env(COST).summary.rpt
				
				get_drc_error_data -all
				open_drc_error_data zroute.err
				set err_data zroute.err
				set type [get_drc_error_types -error_data $err_data {*}]
				report_drc_errors -error_data $err_data -error_type $type -layers {*} -report_type detailed  > DRVs_no_opt_$::env(COST).log

                start_gui
                get_drc_error_data -all
                open_drc_error_data zroute.err
                gui_show_error_data zroute.err
                gui_report_errors -file $::env(DRV_LOG_DIR)
				date

		} elseif { $STAGE == "pnr_3stages" } {
            set postfix ""

			if { ![ file exists $::env(build_name).sdc ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).sdc\n"; exit
			}
			if { ![ file exists $::env(build_name).netlist.v ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).netlist.v\n"; exit
			}
			if { ![ file exists $::env(build_name).variables.tcl ] } {
				puts "\n\[INFO\] run directory should have $::env(build_name).variables.tcl\n"; exit
			}
		
			if {[info exists REVISION] && $REVISION == "MCellPre"} {
				set outDir "data/02_pnr_MCellPre_s"
			} elseif {[info exists REVISION] && $REVISION == "MCellPost"} {
				set outDir "data/02_pnr_MCellPost_s"
			} elseif {[info exists REVISION] && $REVISION == "Popt"} {
				set outDir "data/02_pnr_Popt_s"
			} else {
				set outDir "data/02_pnr_s"
			}
			set DESIGN_LIB $outDir
			
			prc_icc2_setupConfig

            if { [ file exists $outDir/03_Route_from_cts_3_stages${postfix}/design.ndm ] } {
                open_block 03_Route_from_cts_3_stages${postfix}
                if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
            } else {
                if { [ file exists $outDir/03_Clock_opt/design.ndm ] } {
                    open_block 03_Clock_opt
                    if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
                } else {
                    if { [ file exists $outDir/02_Place_opt/design.ndm ] } {
                        open_block 02_Place_opt
                        if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
                    } else {
                        if { [ file exists $outDir/01_Placement/design.ndm ] } {
                            open_block 01_Placement
                            if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
                        } else {
                            if { [ file exists $outDir/00_Place_coarse/design.ndm ] } {
                                open_block 00_Place_coarse
                                if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
                            } else {
                                if { [ file exists $outDir/00_Floorplan/design.ndm ] } {
                                    open_block 00_Floorplan
                                    if { [ file exists "addconfig.tcl" ] } { source addconfig.tcl }
                                } else {
                                    # Read verilog
                                    if {[info exists REVISION] && $REVISION == "MCellPost"} {
                                        read_verilog $::env(build_name).place_opt.v -top $::env(build_name)
                                    } elseif {[info exists REVISION] && $REVISION == "Popt"} {
                                        read_verilog $::env(build_name).graphH.netlist.v -top $::env(build_name)
                                    } else {
                                        read_verilog $::env(build_name).netlist.v -top $::env(build_name)
                                    }
                                    
                                    # Read DEF or create floorplan
                                    if {[info exists REVISION] && $REVISION == "MCellPost"} {
                                        read_def $::env(build_name).place_opt.def
                                    } elseif { [ file exists "floorplan.def" ] } { 
                                        read_def floorplan.def 
                                    } else {	
                                        # Initialize floorplan
                                        if {[info exists REVISION] && $REVISION == "MCellPre"} {
                                            source MCell_data/$::env(build_name).preMerge.icc2.tcl
                                        }
                                        set offset [list $vars(FloorPlan,LeftMargin) $vars(FloorPlan,BottomMargin) $vars(FloorPlan,RightMargin) $vars(FloorPlan,TopMargin)]
                                        set_attribute [get_layers {M1 MINT2 MINT4 MSMG1 MSMG3 MSMG5 MG2}] routing_direction vertical
                                        set_attribute [get_layers {MINT1 MINT3 MINT5 MSMG2 MSMG4 MG1}] routing_direction horizontal
                                        if { $vars(FloorPlan,Type) == "r" } {
                                            initialize_floorplan -core_offset $offset -core_utilization $vars(FloorPlan,var2) -side_ratio [list 1 $vars(FloorPlan,var1)]
                                        } elseif { $vars(FloorPlan,Type) == "d" } {
                                            initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type die
                                        } elseif { $vars(FloorPlan,Type) == "s" } {
                                            initialize_floorplan -core_offset $offset -side_length [list $vars(FloorPlan,var1) $vars(FloorPlan,var2)] -control_type core
                                        }
                                    }
                                    prc_icc2_mmmcConfig
                                    prc_icc2_setPNRmodes
                                    if { [ file exists "config.tcl" ] } { source config.tcl }
                                    
                                    if {[info exists REVISION] && $REVISION == "MCellPost"} {
                                    } else {
                                        save_block -as 00_Floorplan
                                    }
                                }							
                                if {[info exists REVISION] && $REVISION == "MCellPost"} {
                                } else {
                                    # Corase placement
                                    #create_placement -floorplan
                                    set_app_options -name place.fix_hard_macros -value true
                                    create_placement 
                                
                                    # Pin placement
                                    place_pins -self
                                    #save_block -as $outDir/00_Place_coarse
                                    save_block -as 00_Place_coarse
                                }
                            }						
                            ## Placement
                            set_app_options -name opt.common.user_instance_name_prefix -value "placeOpt_"
                            if {[info exists REVISION] && $REVISION == "MCellPost"} {
                            } else {
                                if { [ file exists "config_pre_placement.tcl" ] } { source config_pre_placement.tcl }
                                if {[info exists REVISION] && $REVISION == "placeOnly"} {
                                    place_opt -to initial_place
                                    if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
                                    save_block -as 01_Placement
                                    write_def -version 5.7 $::env(build_name).placeOnly.def
                                    exit
                                } elseif { [ info exists vars(PNR,place_opt_design) ] && $vars(PNR,place_opt_design) == 0 } {
                                    place_opt -to final_place
                                    if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
                                    save_block -as 01_Placement
                                } else {
                                }
                            }
                            #write_def $::env(build_name).place.def
                        }
                        ## pre-CTS opt
                        if {[info exists REVISION] && $REVISION == "MCellPost"} {
                            source MCell_data/$::env(build_name).postMerge.icc2.tcl
                            if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
                            save_block -as 02_Place_opt_merged
                        } else {
                            if { [ info exists vars(PNR,place_opt_design) ] && $vars(PNR,place_opt_design) == 0 } {
                            } else {
                                place_opt
                                if { [ file exists "config_post_placement.tcl" ] } { source config_post_placement.tcl }
                                save_block -as 02_Place_opt
                            }
                        }
                        write_def $::env(build_name).place_opt.def
                    }				
                    ## CTS
                    set_app_options -name opt.common.user_instance_name_prefix -value "clockOpt_"
                    #clock_opt -to route_clock
#						if { [ file exists "config_pre_clock_opt.tcl" ] } { source config_pre_clock_opt.tcl }
#						
#						if {[info exists vars(PNR,clock_opt_design)] && $vars(PNR,clock_opt_design) == 0} {
#							clock_opt -to route_clock
#						} else {
#							clock_opt
#						}
#						
#						if { [ file exists "config_post_clock_opt.tcl" ] } { source config_post_clock_opt.tcl }
#						#save_block -as $outDir/03_Clock_opt
#						
#						if {[info exists vars(PNR,clock_opt_design)] && $vars(PNR,clock_opt_design) == 0} {
#							save_block -as 03_Clock_noOpt
#						} else {
#							save_block -as 03_Clock_opt
#						}
                    clock_opt
                    save_block -as 03_Clock_opt
                    remove_routes -global_route
                    set_app_options -name route.global.force_rerun_after_global_route_opt -value true
#						clock_opt -to route_clock
#						save_block -as 03_Clock_noOpt
                }	
                ## Routing
                remove_routes -global_route
                set_app_options -name route.global.force_rerun_after_global_route_opt -value true
                set_app_options -name opt.common.user_instance_name_prefix -value "routeOpt_"
                if { [ file exists "config_pre_route.tcl" ] } { source config_pre_route.tcl }
                #route_auto -max_detail_route_iterations $vars(PNR,routingIteration)
                route_global
                route_track
                route_detail -max_number_iterations $vars(PNR,routingIteration)
                if { [ file exists "config_post_route.tcl" ] } { source config_post_route.tcl }
                #save_block -as $outDir/03_Route_from_cts_3_stages
                save_block -as 03_Route_from_cts_3_stages${postfix}
            }
#            start_gui
            get_drc_error_data -all
            open_drc_error_data zroute.err
#            gui_show_error_data zroute.err
#            gui_report_errors -file 03_Route_from_cts_3_stages${postfix}.log
#            stop_gui

            report_drc_errors -error_data zroute.err > old.log


            #set save_block_name 03_Route_from_cts_3_stages${postfix}
            set save_block_name old
            #source /home/users/suwankim/CAD_choi/scripts/report_congestion.tcl > ${save_block_name}.cong
            report_design > ${save_block_name}.wire
            report_timing > ${save_block_name}.timing
            report_power > ${save_block_name}.power
            report_qor > ${save_block_name}.qor


#            start_gui
#            get_drc_error_data -all
#            open_drc_error_data zroute.err
#            gui_show_error_data zroute.err
#            gui_report_errors -file old_drv.log
#            stop_gui
                
          #	## Wrap-up
#			if { [ file exists "config_pre_wrapup.tcl" ] } { source config_pre_wrapup.tcl }
#			update_timing
#			report_clock_qor -all > $outDir/$::env(build_name).clock_qor.icc2
#			report_timing -nets -significant_digits	6  > $outDir/$::env(build_name).timing.icc2
#			report_power -significant_digits 6 > $outDir/$::env(build_name).power.icc2
#			report_power -cell_power  -significant_digits 6 >  $outDir/$::env(build_name).cellPower.icc2
#			report_power -net_power  -significant_digits 6 >  $outDir/$::env(build_name).netPower.icc2
#	
#			if {[info exists REVISION]} {
#				sh mkdir -p SPEF/$REVISION
#				write_parasitics -compress -output SPEF/$REVISION/$::env(build_name).final
#				write_verilog $::env(build_name)_$REVISION.final.v
#				write_def -version 5.7 $::env(build_name)_$REVISION.final.def
#				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name).summary.rpt
#			} else {
#				sh mkdir -p SPEF
#				write_parasitics -compress -output SPEF/$::env(build_name).final
#				write_verilog $::env(build_name).final.v
#				write_def -version 5.7 $::env(build_name).final.def
#				report_design -floorplan -netlist -routing -library -nosplit > $outDir/$::env(build_name).summary.rpt
#			}
			
            #get_drc_error_data -all
            #open_drc_error_data zroute.err
            #set err_data zroute.err
            #set type [get_drc_error_types -error_data $err_data {*}]
            #report_drc_errors -error_data $err_data -error_type $type -layers {*} -report_type detailed  >> DRVs.log

            #start_gui
            #get_drc_error_data -all
            #open_drc_error_data zroute.err
            #gui_show_error_data zroute.err
            #gui_report_errors -file DRVs_summary.log


		}  
	} \
	elseif { $TOOL == "PT" } {
		prc_setLinkTargetLibs
		if {[info exists REVISION] && $REVISION == "MCellPre"} {
			set outDir "data/03_sta_MCellPre_s"
		} elseif {[info exists REVISION] && $REVISION == "MCellPost"} {
			set outDir "data/03_sta_MCellPost_s"
		} elseif {[info exists REVISION] && $REVISION == "Popt"} {
			set outDir "data/03_sta_Popt_s"
		} else {
			set outDir "./data/03_sta_s"
		}

		sh mkdir -p $outDir

		if {[info exists REVISION]} {
			read_verilog $::env(build_name)_$REVISION.final.v	
		} else {
			read_verilog $::env(build_name).final.v	
		}
		current_design $::env(build_name)
		link_design
		
		if { [ file exists "$::env(build_name)_ana.sdc" ] } {
			source $::env(build_name)_ana.sdc
		} else {
			source $::env(build_name).sdc
		}
		
		prc_PT_readParasitics
		
		set timing_save_pin_arrival_and_slack		true
		set timing_save_pin_arrival_and_required	true
		report_units
		
		if { [ file exists "sta_timing_options.tcl" ] } { source sta_timing_options.tcl }
	
		report_timing		-nets \
					-nosplit \
					-capacitance \
					-transition_time \
					-input_pins \
					-significant_digits	6	> $outDir/$::env(build_name).timing
		prc_reportTNS
		report_clock_timing	-type	summary \
					-significant_digits	6 \
					-nosplit	> $outDir/$::env(build_name).clock
		
		
		puts "Performing Power Analysis"
		set power_enable_analysis	true
		set power_analysis_mode	averaged
		set power_clock_network_include_register_clock_pin_power	false
		prc_Snps_setSwitchingActivity
		if { [ file exists "sta_power_options.tcl" ] } { source sta_power_options.tcl }
		update_power
		report_switching_activity
		report_power -verbose	>  $outDir/$::env(build_name).power
		report_power -cell_power >  $outDir/$::env(build_name).cellPower
		report_power -net_power >  $outDir/$::env(build_name).netPower
		prc_PT_report
		sh mv $::env(build_name).benchmark $outDir
		
		save_session $outDir/$::env(build_name)_sta
	}
}

date
#quit!
#exit
