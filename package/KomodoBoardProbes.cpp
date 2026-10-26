// SPDX-License-Identifier: MIT
// komodo board hooks called by the late legacy-display probe (LegacyDisplayProbe.cpp). sheng fills
// these with its Novatek touch, Qualcomm cpufreq and Adreno power probes; komodo has none of those yet.
// The Synaptics TCM touch probe over the Samsung USI SPI controller lands here when written.
extern "C" void native_touch_probe(void) {}
extern "C" void sheng_cpufreq_probe(void) {}
extern "C" void sheng_gpu_power_probe(void) {}
