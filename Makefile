# Smoothieware x86 simulator build.
#   make                                                 firmware: Smoothieware's edge branch, cloned into fw/ on first use
#   make SMOOTHIE_SRC=/path/to/Smoothieware BUILD=build/<name>   firmware: your own checkout
# The firmware tree is never modified: it is copied to $(BUILD)/stage, then overlay/ is laid over it.
SMOOTHIE_REPO ?= https://github.com/Smoothieware/Smoothieware
SMOOTHIE_BRANCH ?= edge
BUILD ?= build
HERE := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ifeq ($(origin SMOOTHIE_SRC),undefined)
SMOOTHIE_SRC := $(HERE)fw
# The default firmware tree: a shallow clone, made only when fw/ has no checkout yet.
$(SMOOTHIE_SRC)/src/main.cpp:
	git clone --depth 1 --branch $(SMOOTHIE_BRANCH) $(SMOOTHIE_REPO) $(SMOOTHIE_SRC)
endif
STAGE := $(BUILD)/stage
CXX ?= g++
# NO_* flags remove modules that need hardware this simulator cannot fake (yet).
NOFLAGS ?= -DNONETWORK
EXTRA ?=
# Firmware trees whose Block keeps axis records only for the motors that move (is_active/axis/set_active) need SIM_SPARSE_BLOCKS;
# upstream edge keeps one tick_info record per actuator. Detected from the firmware's own Block.h.
BLOCK_API := $(if $(shell grep -s -l is_active $(SMOOTHIE_SRC)/src/modules/robot/Block.h),-DSIM_SPARSE_BLOCKS)
# COVERAGE=1 (default) builds with gcov counters so the modules checker can tell which handler lines the workload ran.
COVERAGE ?= 1
# RACE=1: race mode, the step ISR can preempt the firmware in the middle of a Block flag read-modify-write (see shim/sim_race.h).
RACE ?= 0
# EXTRA_FILES: space separated .cpp/.h/.c paths relative to SMOOTHIE_SRC that live outside src/ (for example mbed/src/cpp/SWSPI.cpp
# changed by a PR); they are copied to src/extra/ in the stage so they are compiled and found by #include.
EXTRA_FILES ?=
CXXFLAGS := -Dinfinityf=__builtin_inff -include vector -include algorithm -include sim_force.h -std=gnu++14 -include cstdint -include cstddef -include cstdio -include cstring -include cstdlib -include cmath -include string -O1 -g -w -fpermissive -DCHECKSUM_USE_CPP -DDEFAULT_SERIAL_BAUD_RATE=9600 \
  $(if $(filter 1,$(COVERAGE)),-fprofile-arcs -ftest-coverage) -DMAX_ROBOT_ACTUATORS=$(or $(AXIS),5) -D__GITVERSIONSTRING__=\"sim\" $(NOFLAGS) $(BLOCK_API) $(EXTRA) $(if $(filter 1,$(RACE)),-DSIM_RACE)
EXCLUDE_DIRS := modules/utils/panel/screens/3dprinter libs/USBDevice libs/Network libs/ChaNFS testframework libs/SDFAT.cpp libs/Watchdog.cpp \
  libs/ahbmalloc.cpp libs/ADC main.cpp libs/MRI_Hooks.cpp modules/utils/PlayLed

all: $(BUILD)/smoothie-sim
stage: $(STAGE)/.done
$(STAGE)/.done: $(HERE)tools/stage_patch.py $(shell find $(HERE)overlay -type f) $(SMOOTHIE_SRC)/src/main.cpp
	rm -rf $(STAGE) && mkdir -p $(STAGE) && cp -r $(SMOOTHIE_SRC)/src $(STAGE)/src
	cp -r $(HERE)overlay/. $(STAGE)/src/
	for f in $(EXTRA_FILES); do mkdir -p $(STAGE)/src/extra/$$(dirname $$f) && cp $(SMOOTHIE_SRC)/$$f $(STAGE)/src/extra/$$f; done
	python3 $(HERE)tools/stage_patch.py $(STAGE)/src
	$(if $(filter 1,$(RACE)),python3 $(HERE)tools/stage_patch_race.py $(STAGE)/src)
	touch $@

SRCS = $(shell cd $(STAGE)/src && find . -name '*.cpp' | sed 's|^\./||' | grep -v $(foreach d,$(EXCLUDE_DIRS),-e '^$(d)')) 
INCS = $(addprefix -I,$(HERE)shim $(STAGE)/src $(shell find $(STAGE)/src -type d))

OBJS = $(addprefix $(BUILD)/obj/,$(SRCS:.cpp=.o))
SIMOBJS = $(patsubst $(HERE)sim/%.cpp,$(BUILD)/simobj/%.o,$(wildcard $(HERE)sim/*.cpp))

$(BUILD)/smoothie-sim: $(STAGE)/.done
	$(MAKE) -f $(HERE)Makefile RACE=$(RACE) BUILD=$(BUILD) SMOOTHIE_SRC=$(SMOOTHIE_SRC) COVERAGE=$(COVERAGE) EXTRA_FILES='$(EXTRA_FILES)' link
.PHONY: $(BUILD)/smoothie-sim link
link: $(OBJS) $(SIMOBJS)
	$(CXX) $(if $(filter 1,$(COVERAGE)),--coverage) -Wl,--wrap=malloc,--wrap=calloc,--wrap=realloc,--wrap=free -o $(BUILD)/smoothie-sim $(OBJS) $(SIMOBJS)
$(BUILD)/obj/%.o: $(STAGE)/src/%.cpp $(wildcard $(HERE)shim/*.h)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(INCS) -c $< -o $@
$(BUILD)/simobj/%.o: $(HERE)sim/%.cpp $(wildcard $(HERE)sim/*.h) $(wildcard $(HERE)shim/*.h)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(INCS) -c $< -o $@
