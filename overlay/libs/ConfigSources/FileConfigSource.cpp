// simulator stub: the firmware config is injected through the embedded config.default buffer, no config files exist
#include "FileConfigSource.h"
FileConfigSource::FileConfigSource(string f, const char *) : config_file(f), config_file_found(false) {}
void FileConfigSource::transfer_values_to_cache(ConfigCache *) {}
void FileConfigSource::transfer_values_to_cache(ConfigCache *, const char *) {}
bool FileConfigSource::is_named(uint16_t) { return false; }
bool FileConfigSource::write(string, string) { return false; }
string FileConfigSource::read(uint16_t *) { return ""; }
bool FileConfigSource::has_config_file() { return false; }
void FileConfigSource::try_config_file(string) {}
string FileConfigSource::get_config_file() { return config_file; }
bool FileConfigSource::readLine(string &, int, FILE *) { return false; }
