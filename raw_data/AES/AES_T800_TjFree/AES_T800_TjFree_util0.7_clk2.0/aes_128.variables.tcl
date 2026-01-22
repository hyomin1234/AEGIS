##################
#
# Design variables
#
##################

####### System ######
### Cpu usage (recommend: 4~8)
set vars(Design,cpuNo)	4
#####################

#### Library units - check .lib ####
# Common (Cadence & Synopsys)
set vars(LibUnit,Time) 1ps
set vars(LibUnit,Cap) 1pF
####################################

########## SYN ##########
## clock pin name in RTL
set vars(Syn,clkName) $::env(clkName)
## reset pin name in RTL
set vars(Syn,rstName) $::env(rstName)

## clock period (in ns)
## (Applied only in synthesis step) ##
set vars(Syn,clkPeriod) $::env(CLK)

## 0: unflatten, 1: flatten design 
set vars(Syn,flatten) 1

## 0: remain bus (ex. [15:0]), 1: remove bus (ex. _15, _14, _13, ..., _0)
set vars(Syn,removeBus) 1
#########################

######## PNR/STA ########
#### Process node (XX nm) ####
# Common (Cadence & Synopsys)
# Sometimes it is different, for some PDK..
# ex. FreePDK15 (NanGate15) - please set as 's14'.
set vars(LibUnit,Process) 7
##############################

#### Floorplan variables ####
# Common (Cadence & Synopsys)
# Type: r(atio), d(ie size), s(ize of core)
# Type |  var1  |    var2
# --------------------------
#   r  | Aspect | Std. cell
#	   |ratio(H)|  density
#---------------------------
#   d  | Width  |  Height
#   s  | Width  |  Height
set vars(FloorPlan,Type) r
set vars(FloorPlan,var1) 1
set vars(FloorPlan,var2) $::env(UTIL)

## die-core distance in 4 directions 
set vars(FloorPlan,LeftMargin) 5
set vars(FloorPlan,BottomMargin) 5
set vars(FloorPlan,RightMargin) 5
set vars(FloorPlan,TopMargin) 5
#############################


#### Clock uncertainty variables for each stage ####
# Common (Cadence & Synopsys)
set vars(ClockUncertainty,preCTS) 0
set vars(ClockUncertainty,CTS) 0
set vars(ClockUncertainty,postCTS) 0
set vars(ClockUncertainty,postRoute) 0
####################################################

#### Switching activity variables for analysis (PnR/STA) ####
# Common (Cadence & Synopsys)
# FF toggle rate
set vars(SwitchingActivity,RegToggle) 0.1
# Input toggle rate
set vars(SwitchingActivity,IpToggle) 0.1
# Clock toggle rate (ex. 2.0: normal clock wave)
set vars(SwitchingActivity,ClkToggle) 2.0
# Ratio of logic '1' in the full time (ex. 0.5: half '1', half '0')
set vars(SwitchingActivity,DutyRatio) 0.5
##################################################

#### Extraction engine efforts ####
# Cadence only
#IQRC(effort: high) or TQRC(effort: medium)
set vars(ExtractionEngine,postRoute) "TQRC"
###################################

#### Extraction engine RC scaling factor ####
# Cadence only
set vars(ExtractionEngine,Scaling) 1
#############################################

#### Options for P&R ####
# Common (Cadence & Synopsys)
# Max density in a local bin
## For Synopsys ICC2, it is recommended to set it 0.0, which makes ICC2 to automatically set the density.
set vars(PNR,placeMaxDensity) 0.0
# Min/Max routing layer
# - ICC2: write layer name
# - INN: write layer name or number (ex. bottom-most layer = 1)
#set vars(PNR,maxRouteLayer) 5
set vars(PNR,maxRouteLayer) 3
set vars(PNR,minRouteLayer) 2
# routing iteration count (default: 10(INN), 20(ICC2))
set vars(PNR,routingIteration) 1
# 0 --> do NOT perform pre-CTS optimization
# else --> perform opt.
set vars(PNR,place_opt_design) 0

# Cadence only
set vars(PNR,maxPinRouteLayer) 3
set vars(PNR,minPinRouteLayer) 2
set vars(PNR,leakageToDynamicRatio) 0.1
set vars(PNR,postRouteHold)	    0
set vars(CCOpt,top_top)			3
set vars(CCOpt,top_bottom)		3
set vars(CCOpt,trunk_top)		3
set vars(CCOpt,trunk_bottom)	2
set vars(CCOpt,leaf_top)		2
set vars(CCOpt,leaf_bottom)		2

#set vars(PNR,maxPinRouteLayer) 6
#set vars(PNR,minPinRouteLayer) 2
#set vars(PNR,leakageToDynamicRatio) 0.1
#set vars(PNR,postRouteHold)	    0
#set vars(CCOpt,top_top)			6
#set vars(CCOpt,top_bottom)		6
#set vars(CCOpt,trunk_top)		6
#set vars(CCOpt,trunk_bottom)	2
#set vars(CCOpt,leaf_top)		2
#set vars(CCOpt,leaf_bottom)		2


# Synopsys only
# 0 --> do NOT perform post-CTS/post-route optimization
# else --> perform opt.
set vars(PNR,clock_opt_design) 0
set vars(PNR,route_opt_design) 0
# 1 --> run concurrent data opimization during CTS
set vars(CTS,ccdopt_design)	0

# Buffer list for CTS (Cadence only)
set vars(tech,cts_buffer_cells)		[list \
		
									]
set vars(tech,cts_inverter_cells)	[list \
									]
#########################

### Filler cell list (Optional) ###
# Common (Cadence & Synopsys)
set vars(tech,filler_cells)		[list \
						]
#####################
