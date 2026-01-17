# BarnabeeNet Hardware Specifications

**Document Version:** 1.0  
**Last Updated:** January 16, 2026  
**Author:** Thom Fife  
**Purpose:** Complete hardware specifications, requirements, and deployment guidance for BarnabeeNet

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Production Server: Beelink EQi12](#production-server-beelink-eqi12)
4. [Compute Server: Gaming PC](#compute-server-gaming-pc)
5. [Input/Output Devices](#inputoutput-devices)
6. [Network Infrastructure](#network-infrastructure)
7. [Power and Environmental](#power-and-environmental)
8. [Storage Architecture](#storage-architecture)
9. [Virtualization: Proxmox Configuration](#virtualization-proxmox-configuration)
10. [Performance Benchmarks & Capacity Planning](#performance-benchmarks--capacity-planning)
11. [Bill of Materials](#bill-of-materials)
12. [Upgrade Paths](#upgrade-paths)
13. [Hardware Compatibility Matrix](#hardware-compatibility-matrix)

---

## Executive Summary

BarnabeeNet employs a **two-tier compute architecture** optimized for the distinct requirements of always-on edge processing and on-demand heavy inference:

| Tier | Hardware | Role | Availability |
|------|----------|------|--------------|
| **Tier 1** | Beelink EQi12 Mini PC | Always-on processing, HA core, fast STT/TTS | 24/7/365 |
| **Tier 2** | Gaming PC (RTX 4070 Ti) | Heavy LLM inference, training, development | On-demand |

This architecture provides:
- **Sub-500ms latency** for voice commands via local edge processing
- **$0 marginal cost** for routine operations (local models)
- **Graceful degradation** when Tier 2 is unavailable
- **~$15-25/month** typical power costs for 24/7 operation

### Hardware Budget Summary

| Category | Estimated Cost | Notes |
|----------|---------------|-------|
| Production Server (Beelink) | $350-450 | New; used available ~$250 |
| Gaming PC (existing) | $0 | Assumes existing hardware |
| Gaming PC (new build) | $2,500-3,500 | If building new |
| Input/Output Devices | $800-1,200 | AR glasses, wearables, displays |
| Network Infrastructure | $100-300 | Switches, cables, access points |
| **Total (existing gaming PC)** | **$1,250-1,950** | |
| **Total (new gaming PC)** | **$3,750-5,450** | |

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      BARNABEENET HARDWARE TOPOLOGY                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    TIER 1: EDGE PROCESSING                        │   │
│  │                    (Always-On, Low-Power)                         │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │  BEELINK EQi12                                              │  │   │
│  │  │  ├─ Intel Core i3-1220P (10C/12T, 4.4GHz)                  │  │   │
│  │  │  ├─ 24GB LPDDR5 5200MHz                                    │  │   │
│  │  │  ├─ 500GB PCIe 4.0 NVMe (expandable to 4TB)               │  │   │
│  │  │  ├─ Dual Gigabit LAN / WiFi 6 / BT 5.2                    │  │   │
│  │  │  └─ 15-25W typical power draw                              │  │   │
│  │  │                                                              │  │   │
│  │  │  RUNS:                                                       │  │   │
│  │  │  ├─ Proxmox VE (hypervisor)                                │  │   │
│  │  │  ├─ Home Assistant VM                                       │  │   │
│  │  │  ├─ BarnabeeNet Integration                                │  │   │
│  │  │  ├─ Faster-Whisper STT                                     │  │   │
│  │  │  ├─ Piper TTS                                              │  │   │
│  │  │  ├─ ECAPA-TDNN Speaker ID                                  │  │   │
│  │  │  ├─ Redis (working memory)                                 │  │   │
│  │  │  └─ SQLite (persistent storage)                            │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    │ Gigabit Ethernet                    │
│                                    ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   TIER 2: HEAVY COMPUTE                          │   │
│  │                   (On-Demand, High-Power)                        │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │  GAMING PC                                                   │  │   │
│  │  │  ├─ Intel Core i9-14900KF (24C/32T, 6.0GHz)               │  │   │
│  │  │  ├─ 128GB DDR5-5600                                        │  │   │
│  │  │  ├─ NVIDIA RTX 4070 Ti (12GB VRAM)                        │  │   │
│  │  │  ├─ ~11TB NVMe Storage                                     │  │   │
│  │  │  └─ 450-650W typical power draw                            │  │   │
│  │  │                                                              │  │   │
│  │  │  RUNS:                                                       │  │   │
│  │  │  ├─ Local LLM Inference (Llama, Mistral)                   │  │   │
│  │  │  ├─ Speaker Embedding Training                              │  │   │
│  │  │  ├─ Memory Consolidation Jobs                              │  │   │
│  │  │  ├─ Model Fine-Tuning                                       │  │   │
│  │  │  ├─ Vibe Coding / Development                              │  │   │
│  │  │  └─ Azure ML Benchmarking                                   │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Production Server: Beelink EQi12

### Overview

The Beelink EQi12 serves as BarnabeeNet's always-on edge processing unit. Selected for its optimal balance of:
- **Performance**: 10-core/12-thread CPU handles concurrent STT, speaker ID, and routing
- **Memory**: 24GB LPDDR5 enables multiple models resident in RAM
- **Power efficiency**: 15-25W typical allows continuous operation
- **Form factor**: Compact (4.96" × 4.96" × 1.74") for unobtrusive placement
- **Connectivity**: Dual LAN for network segmentation

### Detailed Specifications

#### Processor

| Attribute | Specification |
|-----------|--------------|
| Model | Intel Core i3-1220P (Alder Lake-P) |
| Architecture | Intel 7 (10nm Enhanced SuperFin) |
| Cores/Threads | 10 cores / 12 threads |
| P-Cores | 2 Performance cores @ 3.3-4.4 GHz |
| E-Cores | 8 Efficient cores @ 2.3-3.3 GHz |
| L3 Cache | 12 MB Intel Smart Cache |
| TDP | 28W base, 64W max turbo |
| Process | TSMC 10nm FinFET |
| Integrated Graphics | Intel UHD Graphics (64 EUs @ 1.10 GHz) |

**Performance Notes**:
- 24% improved performance over Core i5-11320H (per Beelink benchmarks)
- Hybrid architecture (P-cores + E-cores) optimizes for mixed workloads
- E-cores handle background tasks while P-cores handle burst inference
- Sustained multi-threaded performance suitable for concurrent STT + Speaker ID

#### Memory

| Attribute | Specification |
|-----------|--------------|
| Capacity | 24GB (2 × 12GB) |
| Type | LPDDR5 |
| Speed | 5200 MHz |
| Brand | Micron |
| Configuration | Dual-channel, soldered to motherboard |
| Bandwidth | ~83.2 GB/s theoretical |

**Memory Allocation Plan**:
```
┌─────────────────────────────────────────────────────┐
│              24GB LPDDR5 ALLOCATION                  │
├─────────────────────────────────────────────────────┤
│  Proxmox Host          │  2 GB                      │
│  Home Assistant VM     │  8 GB                      │
│  ├─ HA Core           │  2 GB                      │
│  ├─ BarnabeeNet       │  2 GB                      │
│  ├─ Faster-Whisper    │  1.5 GB (distil-small)    │
│  ├─ Piper TTS         │  0.5 GB                    │
│  ├─ ECAPA-TDNN        │  1 GB                      │
│  └─ Redis             │  1 GB                      │
│  Reserved/Buffer      │  14 GB                     │
│  ├─ SQLite/Embeddings │  2 GB                      │
│  ├─ Model Hot-Swap    │  4 GB                      │
│  └─ System Buffer     │  8 GB                      │
└─────────────────────────────────────────────────────┘
```

**IMPORTANT**: RAM is soldered and cannot be upgraded. The 24GB configuration is essential; lower-RAM variants (16GB) are not recommended.

#### Storage

| Attribute | Specification |
|-----------|--------------|
| Primary SSD | 500GB M.2 2280 NVMe PCIe 4.0 x4 |
| Read Speed | Up to 5,000 MB/s |
| Write Speed | Up to 4,000 MB/s |
| Expansion Slots | 2 × M.2 2280 PCIe 4.0 |
| Maximum Capacity | 4TB (2 × 2TB) |

**Storage Allocation**:
```
┌─────────────────────────────────────────────────────┐
│              500GB PRIMARY SSD LAYOUT                │
├─────────────────────────────────────────────────────┤
│  Proxmox VE OS        │  32 GB                      │
│  Home Assistant VM    │  64 GB                      │
│  ├─ HA OS            │  32 GB                      │
│  ├─ Configuration    │  8 GB                       │
│  ├─ Media/Recordings │  16 GB                      │
│  └─ Logs             │  8 GB                       │
│  BarnabeeNet Data    │  100 GB                     │
│  ├─ SQLite DBs       │  20 GB                      │
│  ├─ Model Cache      │  50 GB                      │
│  └─ Embeddings       │  30 GB                      │
│  Reserved            │  304 GB                     │
└─────────────────────────────────────────────────────┘
```

**Recommended Expansion**: Add 1TB NVMe for model storage and backups.

#### Connectivity

| Interface | Specification | BarnabeeNet Use |
|-----------|--------------|-----------------|
| Ethernet 1 | Gigabit (1000 Mbps) | LAN / IoT VLAN |
| Ethernet 2 | Gigabit (1000 Mbps) | Management / Gaming PC |
| WiFi | Intel AX200, WiFi 6 (802.11ax) | Backup / Mobile devices |
| Bluetooth | 5.2 | Headset, wearables |
| USB 3.2 Gen2 | 3 × Type-A (10 Gbps) | Peripherals, Zigbee |
| USB 2.0 | 1 × Type-A (480 Mbps) | Low-speed devices |
| USB-C | 1 × Data only (10 Gbps) | External storage |
| HDMI | 2 × HDMI 2.0 (4K@60Hz) | Monitoring displays |
| Audio | 3.5mm combo jack | Debug/monitoring |

#### Thermal & Power

| Attribute | Specification |
|-----------|--------------|
| Cooling | Heat pipe + silent fan + heat fins |
| Noise Level | Near-silent operation |
| Power Supply | Built-in 85W PSU |
| Typical Power Draw | 15-25W (idle to moderate load) |
| Peak Power Draw | ~60W (sustained burst) |
| Input Voltage | 100-240V AC |

**Thermal Management Notes**:
- Bottom air intake with dust filter
- Heat pipe directly contacts CPU
- BIOS fan curve adjustable for noise/thermal balance
- Thermal throttling may occur under sustained heavy loads (per reviews)
- For 24/7 operation, consider elevated mounting for airflow

#### Physical

| Attribute | Specification |
|-----------|--------------|
| Dimensions | 4.96" × 4.96" × 1.74" (126 × 126 × 44mm) |
| Weight | 1.15 lbs (520g) |
| VESA Mount | 75mm × 75mm compatible |
| Color | Black |

### Server Features for BarnabeeNet

The Beelink EQi12 includes critical server-oriented features:

| Feature | Status | BarnabeeNet Application |
|---------|--------|------------------------|
| Wake-on-LAN (WoL) | ✅ Supported | Remote power-on after maintenance |
| PXE Boot | ✅ Supported | Network-based OS deployment |
| RTC Wake | ✅ Supported | Scheduled power-on for maintenance |
| Auto Power On | ✅ Supported* | Automatic restart after power loss |

*Note: Auto Power On requires contacting Beelink support with device barcode for configuration instructions.

### Linux Compatibility

The Beelink EQi12 has confirmed Linux compatibility:

| Distribution | Status | Notes |
|--------------|--------|-------|
| Ubuntu 22.04/24.04 | ✅ Full support | All hardware works out-of-box |
| Fedora 41 | ✅ Full support | "Works out of the box, no manual config" |
| Proxmox VE 8.x | ✅ Full support | Recommended for BarnabeeNet |
| Debian 12 | ✅ Full support | Base for Proxmox |

---

## Compute Server: Gaming PC

### Overview

The Gaming PC serves as BarnabeeNet's heavy compute tier, activated on-demand for:
- Complex LLM inference requiring GPU acceleration
- Speaker embedding training and enrollment
- Memory consolidation batch jobs
- Model fine-tuning experiments
- Development and testing workflows

### Detailed Specifications

#### Processor

| Attribute | Specification |
|-----------|--------------|
| Model | Intel Core i9-14900KF |
| Architecture | Raptor Lake Refresh |
| Cores/Threads | 24 cores / 32 threads |
| P-Cores | 8 @ 3.2-6.0 GHz |
| E-Cores | 16 @ 2.4-4.4 GHz |
| L3 Cache | 36 MB Intel Smart Cache |
| TDP | 125W base, 253W max turbo |
| Integrated Graphics | None (F-suffix) |

**CPU Selection Rationale**:
- High single-thread performance for development tasks
- Massive multi-thread capability for parallel processing
- E-cores handle background services during LLM inference
- Thermal headroom for sustained workloads

#### Graphics Card

| Attribute | Specification |
|-----------|--------------|
| Model | NVIDIA GeForce RTX 4070 Ti |
| Architecture | Ada Lovelace (AD104) |
| CUDA Cores | 7,680 |
| Tensor Cores | 240 (4th Gen) |
| VRAM | 12 GB GDDR6X |
| Memory Bus | 192-bit |
| Memory Bandwidth | 504 GB/s |
| TDP | 285W |
| PCIe | 4.0 x16 |

**LLM Inference Performance** (based on benchmarks):

| Model | Quantization | Tokens/sec | VRAM Usage |
|-------|-------------|------------|------------|
| Llama 3 8B | Q4_K_M | ~82 tok/s | ~5 GB |
| Llama 3 8B | FP16 | OOM | >12 GB |
| Mistral 7B | Q4_K_M | ~85 tok/s | ~4.5 GB |
| Phi-3.5 3.8B | Q8 | ~120 tok/s | ~4 GB |
| Llama 2 13B | Q4_K_M | ~45 tok/s | ~8 GB |
| Llama 2 22B | Q3 | ~25 tok/s | ~11 GB |

**Key Insight**: The RTX 4070 Ti's 12GB VRAM is the primary constraint. Models must be quantized (typically Q4) to fit. For larger models (70B+), consider upgrading to RTX 4090 (24GB) or using cloud offload.

#### Memory

| Attribute | Specification |
|-----------|--------------|
| Capacity | 128 GB |
| Type | DDR5-5600 |
| Configuration | 4 × 32 GB |
| Bandwidth | ~89.6 GB/s theoretical |

**Memory Allocation**:
- 64 GB available for CPU-offloaded model layers
- 32 GB for development environments
- 32 GB for system and caching

#### Storage

| Drive | Capacity | Interface | Role |
|-------|----------|-----------|------|
| Primary NVMe | 2 TB | PCIe 5.0 x4 | OS, active models |
| Secondary NVMe | 4 TB | PCIe 4.0 x4 | Model library |
| Tertiary NVMe | 4 TB | PCIe 4.0 x4 | Datasets, backups |
| Archive | 1 TB | PCIe 4.0 x4 | Cold storage |
| **Total** | **~11 TB** | | |

#### Power Supply

| Attribute | Specification |
|-----------|--------------|
| Wattage | 850-1000W recommended |
| Efficiency | 80+ Gold or better |
| Connectors | 1 × 16-pin (12VHPWR) for GPU |

**Power Draw Estimates**:
| State | Power Draw |
|-------|-----------|
| Idle (display off) | ~80W |
| Light use | ~150W |
| Gaming/Inference | 450-650W |
| Peak (stress test) | ~750W |

---

## Input/Output Devices

### Even Realities G1 AR Glasses

#### Overview

The Even Realities G1 provides a discreet heads-up display for BarnabeeNet notifications and visual feedback without requiring screen interaction.

#### Specifications

| Attribute | Specification |
|-----------|--------------|
| Display | Jade Bird Displays MicroLED |
| Resolution | 640 × 480 (partial vertical used) |
| Color | Monochrome green |
| Optics | Diffractive waveguide |
| Connection | Bluetooth (to smartphone) |
| Weight | ~40g (comparable to regular glasses) |
| Battery | ~10 hours typical use |
| Price | $599 (introductory) |

#### Features for BarnabeeNet

| Feature | Application |
|---------|-------------|
| Notifications | Ambient device status, alerts |
| Teleprompter | Script display for Proxy Mode |
| Translation | Real-time subtitle display |
| AI Assistant | ChatGPT/Claude responses on-lens |
| Navigation | Turn-by-turn directions overlay |

#### Integration Approach

```
┌─────────────────────────────────────────────────────┐
│              G1 INTEGRATION FLOW                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  BarnabeeNet → Home Assistant → Phone App → G1      │
│                                                      │
│  Implementation:                                     │
│  1. HA sends notification via mobile app            │
│  2. Phone relays to G1 via Bluetooth               │
│  3. G1 displays on HUD                             │
│                                                      │
│  Limitations:                                        │
│  - No direct BarnabeeNet ↔ G1 connection           │
│  - Phone must be present and connected             │
│  - ~1-2 second latency for notifications           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Compatibility

| Platform | Support |
|----------|---------|
| iOS | ✅ Even Realities App |
| Android | ✅ Even Realities App |
| Home Assistant | Via mobile notifications |

---

### Amazfit Cheetah Pro

#### Overview

The Amazfit Cheetah Pro serves as a wearable input device for BarnabeeNet, enabling silent gesture-based interactions and choice confirmations.

#### Specifications

| Attribute | Specification |
|-----------|--------------|
| Display | 1.45" AMOLED (480 × 480) |
| OS | Zepp OS 4 |
| Processor | Proprietary |
| Memory | ~2GB storage for apps |
| Connectivity | Bluetooth 5.2 BLE, GPS |
| Battery | Up to 14 days typical |
| Water Resistance | 5 ATM |
| Weight | 52g (without strap) |
| Sensors | HR, SpO2, accelerometer, gyroscope, compass |
| Price | ~$230 |

#### BarnabeeNet Input Capabilities

| Input Type | Detection Method | Use Case |
|------------|-----------------|----------|
| Crown Twist | Rotation sensor | Select Yes/No options |
| Button Click | Physical button | Confirm/dismiss actions |
| Motion Shake | Accelerometer | Quick dismiss/toggle |
| Voice (Zepp Flow) | Microphone | Voice commands |
| Touch | Screen tap | UI interaction |

#### Integration Options

**Option A: Gadgetbridge (Recommended)**
- Open-source, cloud-free
- Polling-based detection (~500ms intervals)
- Full notification control
- Custom app development possible

**Option B: Zepp OS SDK**
- Native development
- Better performance
- Requires Zepp developer account
- Cloud dependency for some features

#### Polling Architecture

```python
# Gadgetbridge polling approach
GESTURE_POLL_INTERVALS = {
    'idle': 10000,      # 10 seconds when inactive
    'armed': 500,       # 500ms when expecting input
    'active': 100,      # 100ms during active gesture
}

# State machine
class GestureDetector:
    def __init__(self):
        self.state = 'idle'
        self.last_activity = time.now()
    
    def poll(self):
        # Poll accelerometer/buttons
        gesture = self.read_sensors()
        
        if gesture.detected:
            self.state = 'active'
            return gesture
        
        # Transition back to idle after timeout
        if time.now() - self.last_activity > 30:
            self.state = 'idle'
        
        return None
```

#### Battery Impact

| Polling Rate | Estimated Battery Impact |
|-------------|-------------------------|
| 10s idle | Minimal (<5% additional drain) |
| 500ms armed | Moderate (~10-15% additional drain) |
| Continuous 100ms | Significant (~25-30% additional drain) |

**Recommendation**: Use adaptive polling with "arming" window triggered by notification.

---

### Lenovo ThinkSmart View

#### Overview

The Lenovo ThinkSmart View (CD-18781Y) is a cost-effective touch display repurposed as a Home Assistant dashboard and voice hub. Originally designed for Microsoft Teams, the community has developed custom ROMs enabling full Android functionality.

#### Specifications

| Attribute | Specification |
|-----------|--------------|
| Display | 8" IPS LCD (1280 × 800) |
| Processor | Qualcomm Snapdragon 624 (8-core, 2.0GHz) |
| RAM | 2GB |
| Storage | 8GB eMMC |
| Camera | 5MP wide-angle |
| Microphone | 2 × far-field microphones |
| Speaker | Full-range speaker |
| Connectivity | WiFi 802.11ac, Bluetooth 4.2 |
| Ports | USB-C (power + data) |
| Price | $20-50 (used/refurbished) |

#### Custom ROM Options

| ROM | Base | Status | Recommendation |
|-----|------|--------|----------------|
| Lineage 15.1 | Android 8.1 | ✅ Stable | **Recommended for BarnabeeNet** |
| Android 11 | AOSP | ⚠️ Some issues | Alternative option |
| postmarketOS | Alpine Linux | 🔧 Experimental | For advanced users |
| Stock Firmware | Android 8.1 | ❌ Locked | Not suitable |

#### BarnabeeNet Configuration

**Recommended Stack**:
- **OS**: Lineage 15.1 (Deadman's build)
- **Browser**: Fully Kiosk Browser
- **Dashboard**: Home Assistant Lovelace
- **Voice**: ViewAssist integration or Wyoming satellite

**Flashing Requirements**:
- Windows PC or Linux (Raspberry Pi works)
- QFIL tool for Qualcomm EDL flashing
- USB cable (quality matters!)
- ~30 minutes per device

#### Deployment Locations

| Location | Role | Features Used |
|----------|------|---------------|
| Kitchen | Family hub | Voice, dashboard, timers |
| Office | Work control | Voice, calendar, device status |
| Bedroom | Ambient display | Clock, weather, gentle wake |
| Living Room | Entertainment control | Media, lighting scenes |

#### Known Limitations

- 2GB RAM limits concurrent apps
- 8GB storage fills quickly
- Some units have different screen panels (compatibility issues)
- USB cable quality critical for flashing
- Three-button nav doesn't rotate in landscape

---

### Alexa Devices

#### Integration Approach

BarnabeeNet integrates with existing Alexa devices as voice I/O endpoints while maintaining local processing:

```
┌─────────────────────────────────────────────────────┐
│              ALEXA INTEGRATION FLOW                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  User → Alexa → BarnabeeNet skill → HA → Response   │
│                                                      │
│  Supported devices:                                  │
│  - Echo Dot (all generations)                       │
│  - Echo Show (for visual responses)                 │
│  - Echo (standard)                                  │
│                                                      │
│  Implementation:                                     │
│  - Custom Alexa skill endpoints                     │
│  - Haaska integration                               │
│  - Voice Intent Script triggers                     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Privacy Note**: Audio processed by Amazon for wake word and initial routing, but BarnabeeNet handles complex logic locally.

---

### Bluetooth Headset

#### Requirements

For private voice interaction, BarnabeeNet supports Bluetooth headsets with:

| Feature | Requirement |
|---------|-------------|
| Bluetooth | 5.0+ (for low latency) |
| Codec | aptX Low Latency or LC3 preferred |
| Microphone | Required for voice input |
| Latency | <100ms for natural conversation |

#### Recommended Models

| Model | Type | Latency | Notes |
|-------|------|---------|-------|
| Sony WH-1000XM5 | Over-ear | ~40ms (LDAC) | Premium noise cancellation |
| Jabra Elite 85t | In-ear | ~50ms | Good mic quality |
| Apple AirPods Pro 2 | In-ear | ~80ms | iOS optimized |
| Samsung Galaxy Buds 2 Pro | In-ear | ~50ms | Samsung ecosystem |

#### Integration

```python
# BlueZ integration for headset audio
import bluetooth

def setup_bluetooth_audio():
    """
    Configure Bluetooth headset as primary audio I/O for private mode.
    """
    # Pair and connect headset
    # Route STT input from headset mic
    # Route TTS output to headset speakers
    # Fall back to room speakers if headset disconnects
```

---

## Network Infrastructure

### Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      NETWORK TOPOLOGY                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                    ┌─────────────────┐                                  │
│                    │    Internet     │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │   Router/       │                                  │
│                    │   Firewall      │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│              ┌──────────────┼──────────────┐                           │
│              │              │              │                            │
│     ┌────────▼────┐  ┌──────▼──────┐  ┌───▼────────┐                  │
│     │ Management  │  │   Primary    │  │    IoT     │                  │
│     │   VLAN 10   │  │   VLAN 20    │  │  VLAN 30   │                  │
│     └─────────────┘  └─────────────┘  └────────────┘                  │
│           │                │                 │                          │
│     ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐                   │
│     │  Beelink  │    │  Gaming   │    │  Zigbee/  │                   │
│     │  (Port 1) │    │    PC     │    │  Z-Wave/  │                   │
│     │           │◄──►│           │    │   WiFi    │                   │
│     │  (Port 2) │    │           │    │  Devices  │                   │
│     └───────────┘    └───────────┘    └───────────┘                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### VLAN Configuration

| VLAN | ID | Subnet | Purpose |
|------|-----|--------|---------|
| Management | 10 | 192.168.10.0/24 | Admin access, Beelink port 1 |
| Primary | 20 | 192.168.20.0/24 | User devices, Gaming PC |
| IoT | 30 | 192.168.30.0/24 | Smart devices, sensors |
| Guest | 40 | 192.168.40.0/24 | Visitor access (isolated) |

### Firewall Rules

```
# Core BarnabeeNet firewall rules

# Allow HA from IoT VLAN
iot -> management : tcp/8123 (Home Assistant)
iot -> management : tcp/1883 (MQTT)

# Allow Gaming PC API access
primary -> management : tcp/8080 (BarnabeeNet API)

# Block IoT -> Internet (except NTP, updates)
iot -> internet : DENY except {ntp, firmware-updates}

# Allow cloud LLM access (when needed)
management -> internet : tcp/443 (OpenRouter, Azure)
```

### Bandwidth Requirements

| Flow | Bandwidth | Latency | Priority |
|------|-----------|---------|----------|
| STT Audio | ~256 kbps | <50ms | Critical |
| TTS Audio | ~256 kbps | <50ms | Critical |
| LLM API | ~1 Mbps burst | <200ms | High |
| Device Commands | <10 kbps | <100ms | Critical |
| Model Downloads | Variable | N/A | Low |

---

## Power and Environmental

### Power Budget

| Component | Idle | Typical | Peak |
|-----------|------|---------|------|
| Beelink EQi12 | 8W | 15-25W | 60W |
| Gaming PC | 80W | 150-300W | 750W |
| ThinkSmart View (×4) | 8W | 12W | 20W |
| Network Equipment | 20W | 25W | 30W |
| **Total (Beelink only)** | **36W** | **52W** | **110W** |
| **Total (with Gaming PC)** | **116W** | **252W** | **860W** |

### Monthly Power Cost Estimate

| Scenario | Hours/Day | kWh/Month | Cost ($0.15/kWh) |
|----------|-----------|-----------|------------------|
| Beelink 24/7 | 24 | 18-36 kWh | $2.70-5.40 |
| Gaming PC (2h/day) | 2 | 9-18 kWh | $1.35-2.70 |
| ThinkSmart Views | 24 | 9-14 kWh | $1.35-2.10 |
| Network | 24 | 18-22 kWh | $2.70-3.30 |
| **Total Monthly** | | **54-90 kWh** | **$8-14** |

### UPS Recommendations

| Device | Priority | UPS Size | Runtime Target |
|--------|----------|----------|----------------|
| Beelink + Network | Critical | 600VA | 30+ minutes |
| Gaming PC | Optional | 1500VA | Graceful shutdown |

**Recommended UPS**: APC Back-UPS 600VA or CyberPower CP600LCD

### Environmental Requirements

| Parameter | Beelink EQi12 | Gaming PC |
|-----------|---------------|-----------|
| Operating Temp | 0-40°C (32-104°F) | 10-35°C (50-95°F) |
| Storage Temp | -20-60°C | -20-60°C |
| Humidity | 20-80% non-condensing | 20-80% non-condensing |
| Altitude | <3000m | <3000m |

---

## Storage Architecture

### Data Categories

| Category | Location | Retention | Backup |
|----------|----------|-----------|--------|
| Configuration | Beelink | Permanent | Git + cloud |
| Conversation History | Beelink (SQLite) | 30 days | Daily |
| Semantic Facts | Beelink (SQLite) | Permanent | Daily |
| Model Cache | Beelink + Gaming PC | As needed | None |
| Training Data | Gaming PC | Permanent | Weekly |
| Audit Logs | Beelink | 90 days | Weekly |

### Backup Strategy

```
┌─────────────────────────────────────────────────────┐
│              BACKUP ARCHITECTURE                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  TIER 1: Local Snapshots                            │
│  ├─ Proxmox VM snapshots (daily)                   │
│  ├─ SQLite database dumps (hourly)                 │
│  └─ Retention: 7 days                              │
│                                                      │
│  TIER 2: Local Mirror                               │
│  ├─ Gaming PC rsync (daily)                        │
│  ├─ Configuration + databases                      │
│  └─ Retention: 30 days                             │
│                                                      │
│  TIER 3: Off-site                                   │
│  ├─ Encrypted cloud backup (weekly)               │
│  ├─ Critical configuration only                    │
│  └─ Retention: 1 year                              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## Virtualization: Proxmox Configuration

### VM Layout

| VM | vCPUs | RAM | Storage | Purpose |
|----|-------|-----|---------|---------|
| Home Assistant | 4 | 8 GB | 64 GB | HA OS + BarnabeeNet |
| Development | 2 | 4 GB | 32 GB | Testing (optional) |
| **Reserved** | 4 | 12 GB | - | Buffer for upgrades |

### Proxmox Configuration

```yaml
# /etc/pve/qemu-server/100.conf (Home Assistant VM)
agent: 1
balloon: 0
boot: order=scsi0
cores: 4
cpu: host
memory: 8192
name: homeassistant
net0: virtio=XX:XX:XX:XX:XX:XX,bridge=vmbr0
numa: 0
ostype: l26
scsi0: local-lvm:vm-100-disk-0,size=64G
scsihw: virtio-scsi-pci
smbios1: uuid=xxxxx
```

### Resource Allocation Principles

1. **Disable Ballooning**: Memory-intensive models need consistent RAM
2. **Pin vCPUs**: Ensure P-cores available for inference
3. **Use virtio**: Maximum I/O performance
4. **SSD-backed storage**: NVMe passthrough ideal

---

## Performance Benchmarks & Capacity Planning

### Voice Pipeline Benchmarks (Beelink EQi12)

| Stage | Model | Time | Notes |
|-------|-------|------|-------|
| STT | Faster-Whisper distil-small | ~150ms | 2-second audio |
| Speaker ID | ECAPA-TDNN | ~20ms | Cosine similarity |
| Meta Agent | Rule-based | <5ms | Pattern matching |
| Meta Agent | Phi-3.5 fallback | ~200ms | Ambiguous queries |
| TTS | Piper medium | ~80ms | Short response |
| **Total (fast path)** | | **~255ms** | |
| **Total (with LLM)** | | **~450ms** | |

### Concurrent User Capacity

| Users Speaking Simultaneously | Beelink Performance |
|------------------------------|---------------------|
| 1 | ✅ Full speed |
| 2 | ✅ Slight queuing |
| 3-4 | ⚠️ Noticeable latency |
| 5+ | ❌ Degraded experience |

**Recommendation**: For households with 5+ simultaneous voice users, consider upgrading to Beelink EQi12 with i5-12450H or i7-12650H.

### LLM Inference Benchmarks (Gaming PC)

| Model | Quantization | Prompt Eval | Generation |
|-------|-------------|-------------|------------|
| Phi-3.5 3.8B | Q8 | 3,600 tok/s | 120 tok/s |
| Mistral 7B | Q4_K_M | 3,200 tok/s | 85 tok/s |
| Llama 3 8B | Q4_K_M | 3,650 tok/s | 82 tok/s |
| Llama 2 13B | Q4_K_M | 2,100 tok/s | 45 tok/s |

---

## Bill of Materials

### Minimum Viable BarnabeeNet

| Item | Quantity | Unit Price | Total |
|------|----------|------------|-------|
| Beelink EQi12 (24GB) | 1 | $380 | $380 |
| Lenovo ThinkSmart View | 2 | $35 | $70 |
| USB Zigbee Coordinator | 1 | $25 | $25 |
| Ethernet Cables (Cat 6) | 5 | $5 | $25 |
| UPS (600VA) | 1 | $70 | $70 |
| **Total** | | | **$570** |

### Recommended Configuration

| Item | Quantity | Unit Price | Total |
|------|----------|------------|-------|
| Beelink EQi12 (24GB) | 1 | $380 | $380 |
| 1TB NVMe (expansion) | 1 | $80 | $80 |
| Lenovo ThinkSmart View | 4 | $35 | $140 |
| Amazfit Cheetah Pro | 1 | $230 | $230 |
| Even Realities G1 | 1 | $599 | $599 |
| USB Zigbee Coordinator | 1 | $25 | $25 |
| Managed Switch (8-port) | 1 | $80 | $80 |
| Ethernet Cables | 10 | $5 | $50 |
| UPS (600VA) | 1 | $70 | $70 |
| **Total** | | | **$1,654** |

### Premium Configuration (New Gaming PC)

Add to recommended:

| Item | Quantity | Unit Price | Total |
|------|----------|------------|-------|
| Intel Core i9-14900KF | 1 | $530 | $530 |
| 128GB DDR5-5600 | 1 | $350 | $350 |
| RTX 4070 Ti | 1 | $750 | $750 |
| Z790 Motherboard | 1 | $300 | $300 |
| 2TB NVMe Gen5 | 1 | $200 | $200 |
| 850W PSU | 1 | $130 | $130 |
| Case | 1 | $120 | $120 |
| Cooling | 1 | $100 | $100 |
| **Gaming PC Subtotal** | | | **$2,480** |
| **Grand Total** | | | **$4,134** |

---

## Upgrade Paths

### Beelink Upgrades

| Current | Upgrade | Benefit | Cost |
|---------|---------|---------|------|
| i3-1220P | i5-12450H variant | 25% more multi-thread | +$50-100 |
| i3-1220P | i7-12650H variant | 40% more multi-thread | +$100-150 |
| 500GB SSD | +1TB NVMe | More model storage | $80 |
| 500GB SSD | +2TB NVMe | Full model library | $150 |

### GPU Upgrades

| Current | Upgrade | Benefit | Cost |
|---------|---------|---------|------|
| RTX 4070 Ti (12GB) | RTX 4070 Ti Super (16GB) | +33% VRAM, run 13B FP16 | $300 upgrade |
| RTX 4070 Ti (12GB) | RTX 4090 (24GB) | +100% VRAM, run 22B+ | $1,200 upgrade |
| RTX 4070 Ti (12GB) | Dual 3090 (48GB total) | 70B inference possible | $1,400 used |

### Alternative Edge Servers

| Model | Pros | Cons | Price |
|-------|------|------|-------|
| Minisforum MS-01 | 10G SFP+, more RAM options | Higher power | $600+ |
| Intel NUC 13 Pro | Thunderbolt 4, smaller | Less expansion | $500+ |
| Beelink SER7 | AMD Ryzen 7, 32GB option | Higher TDP | $500+ |

---

## Hardware Compatibility Matrix

### Confirmed Working

| Component | Status | Notes |
|-----------|--------|-------|
| Beelink EQi12 + Proxmox 8 | ✅ | Full functionality |
| Beelink EQi12 + Ubuntu 24.04 | ✅ | All drivers included |
| RTX 4070 Ti + CUDA 12.x | ✅ | Full tensor core support |
| ThinkSmart View + Lineage 15.1 | ✅ | Community ROM |
| Amazfit Cheetah Pro + Gadgetbridge | ✅ | Full feature access |
| Even Realities G1 + Android | ✅ | Via companion app |
| Even Realities G1 + iOS | ✅ | Via companion app |
| ECAPA-TDNN + CPU inference | ✅ | SpeechBrain |
| Faster-Whisper + CPU inference | ✅ | CTranslate2 optimized |

### Known Issues

| Component | Issue | Workaround |
|-----------|-------|------------|
| Beelink EQi12 | Thermal throttling under sustained load | Adjust BIOS fan curve |
| ThinkSmart View | Some units have incompatible screens | Check kernel cmdline |
| ThinkSmart View | USB cable quality issues during flash | Use high-quality cable |
| RTX 4070 Ti | 12GB VRAM limits large models | Quantize to Q4 or lower |
| Amazfit | BLE polling latency | Use adaptive intervals |

---

## Appendix A: Quick Reference Cards

### Beelink EQi12 Quick Reference

```
┌────────────────────────────────────────┐
│      BEELINK EQi12 QUICK REFERENCE     │
├────────────────────────────────────────┤
│ CPU: i3-1220P (10C/12T, 4.4GHz)       │
│ RAM: 24GB LPDDR5 5200MHz (soldered)   │
│ SSD: 500GB PCIe 4.0 (expandable 4TB)  │
│ LAN: 2 × Gigabit                       │
│ WiFi: AX200 (WiFi 6)                  │
│ BT: 5.2                                │
│ USB: 3×3.2, 1×2.0, 1×C                │
│ HDMI: 2 × 4K@60Hz                      │
│ Power: 15-25W typical                  │
│ Size: 4.96" × 4.96" × 1.74"           │
└────────────────────────────────────────┘
```

### RTX 4070 Ti LLM Quick Reference

```
┌────────────────────────────────────────┐
│      RTX 4070 Ti LLM REFERENCE         │
├────────────────────────────────────────┤
│ VRAM: 12GB GDDR6X (504 GB/s)          │
│                                        │
│ MODEL FIT GUIDE:                       │
│ ├─ 7B @ Q4:  ~4.5GB  ✅               │
│ ├─ 7B @ Q8:  ~8GB    ✅               │
│ ├─ 7B @ FP16: ~14GB  ❌               │
│ ├─ 13B @ Q4: ~8GB    ✅               │
│ ├─ 13B @ Q8: ~14GB   ❌               │
│ ├─ 22B @ Q3: ~11GB   ✅               │
│ └─ 70B: Requires offload or cloud     │
│                                        │
│ PERFORMANCE (tok/s generation):        │
│ ├─ 7B Q4:  ~85 tok/s                  │
│ ├─ 13B Q4: ~45 tok/s                  │
│ └─ 22B Q3: ~25 tok/s                  │
└────────────────────────────────────────┘
```

---

## Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial hardware specifications document |

---

*This document provides hardware specifications for BarnabeeNet. For theoretical foundations, see BarnabeeNet_Theory_Research.md. For software architecture, see BarnabeeNet_Technical_Architecture.md.*
