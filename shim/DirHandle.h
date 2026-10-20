#pragma once
// simulator stub: no filesystem listing (mbed dirent has extra fields the host one lacks)
#include <sys/stat.h>
struct dirent { char d_name[256]; int d_isdir; long d_fsize; };
struct sim_DIR;
typedef sim_DIR DIR;
static inline DIR *opendir(const char *) { return 0; }
static inline dirent *readdir(DIR *) { return 0; }
static inline int closedir(DIR *) { return 0; }
