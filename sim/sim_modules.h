#pragma once
#include <string>
class Kernel;
void sim_load_modules(Kernel *kernel, bool all_modules);   // mirrors the module list built in the firmware's main.cpp
void sim_inject_blocks(const std::string &path);           // blocks -> steps checker input
