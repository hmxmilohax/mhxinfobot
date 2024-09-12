import re
from collections import defaultdict

def analyze_log_file(log_file_path):
    # Initialize variables
    custom_config_found = False
    last_core_index = -1
    critical_issues = defaultdict(list)
    game_issues = defaultdict(list)
    non_default_settings = []
    firmware_detected = False
    firmware_version = None
    emulator_info = {"version": "", "cpu": "", "os": "", "gpu": ""}
    language_message = ""
    
    # Sets to track duplicate issues
    onedrive_issues = set()
    graphics_device_notifications = set()

    # Attempt to open and read the log file with different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252']  # Add more encodings if needed
    lines = []
    for encoding in encodings:
        try:
            with open(log_file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
            break  # Exit loop if successful
        except UnicodeDecodeError:
            continue  # Try next encoding
    else:
        return "**Error**: Unable to read the log file with the provided encodings."

    # Check if this is a Rock Band 3 log
    if not any("SYS: Title: Rock Band 3" in line for line in lines) or \
       not any("SYS: Serial: BLUS30463" in line for line in lines):
        return "**Yuck!** This isn't a log for Rock Band 3. Feed me something better."

    # Extract emulator information
    emulator_info["version"] = lines[0].strip() if lines else ""
    emulator_info["cpu"] = lines[1].strip() if len(lines) > 1 else ""
    emulator_info["os"] = lines[2].strip() if len(lines) > 2 else ""

    # Check for GPU information
    gpu_found = False
    for i, line in enumerate(lines):
        if "CFG: Setting the default renderer to Vulkan. Default GPU:" in line:
            gpu_match = re.search(r"Default GPU: '(.*)'", line)
            if gpu_match:
                emulator_info["gpu"] = gpu_match.group(1)
                gpu_found = True
            break  # Stop searching once found
    
    if not gpu_found:
        critical_issues[f"**Vulkan compatible GPU not found!**"].append(f"L-{i}")

    # Check log for firmware version and language, with firmware first
    for line in lines:
        firmware_match = re.search(r"SYS: Firmware version: (\d+\.\d+)", line)
        if firmware_match:
            firmware_version = firmware_match.group(1)
            firmware_detected = True
            if float(firmware_version) < 4.91:
                game_issues[f"**Outdated firmware.** You are on `{firmware_version}`. **Please update to `4.91`.**"].append(f"L-{lines.index(line) + 1}")

        # Check for language setting
        if "Language: Spanish" in line:
            language_message = "Hola. Explica lo que paso. / This user speaks Spanish."

    # Scan the log file for "Used configuration" and track indices
    for i, line in enumerate(lines):
        if "Applying custom config" in line:
            custom_config_found = True
        if "Used configuration" in line:
            last_core_index = i

    # Process log information if custom config was found
    if custom_config_found and last_core_index != -1:
        core_section_lines = lines[last_core_index:]

        high_memory_detected = False
        debug_console_mode_off = False

        # Check for specific conditions in the extracted section
        for i, line in enumerate(core_section_lines, start=last_core_index + 1):
            # Non-critical issues
            if 'CELL_ENOENT, "/dev_hdd0/game/BLUS30463/USRDIR/dx_high_memory.dta"' in line:
                game_issues[f"**High memory file is missing!** Use `!mem`"].append(f"L-{i}")

            # Frame limit settings
            if "Frame limit" in line:
                match = re.search(r"Frame limit:\s*(\d+|Auto|Off)", line, re.IGNORECASE)
                if match:
                    frame_value = match.group(1)
                    if frame_value not in ["Auto", "Off", "60"]:
                        game_issues[f"**Weird Framelimit settings. Set it to `Auto`, `Off`, or `60`.** Yours is on {frame_value}"].append(f"L-{i}")
                else:
                    game_issues[f"**Weird framerate settings detected:** Unknown"].append(f"L-{i}")

            # OpenGL Detect
            if "Renderer: OpenGL" in line:
                game_issues[f"**You're using OpenGL!** You should really be on Vulkan."].append(f"L-{i}")

            # OneDrive install detection
            if "OneDrive" in line:
                if "OneDrive install detected" not in onedrive_issues:
                    onedrive_issues.add("**OneDrive detected!** Please move files to C:\\Games**")
                    game_issues[f"**OneDrive detected!** Please move files to C:\\Games"].append(f"L-{i}")

            # Vblank Rate
            if re.search(r"Vblank Rate: (\d+)", line):
                vblank_frequency  = int(re.search(r"\d+", line).group())
                if vblank_frequency < 60:
                    critical_issues[f"**Vblank should not be below 60**. Set it back to at least 60."].append(f"L-{i}")
                elif vblank_frequency > 60:
                    game_issues[f"Playing on a Vblank above 60 may make pitch detection unreliable and online unstable. I hope you know what you're doing."].append(f"L-{i}")

            # High Audio Buffer Duration
            match = re.search(r"Desired Audio Buffer Duration: (\d+)", line)
            if match:
                buffer_duration = int(match.group(1))
                if buffer_duration >= 100:
                    game_issues[f"**Audio Buffer is quite high.** Consider lowering it to 32. It's set to {buffer_duration} ms"].append(f"L-{i}")

            # Fullscreen settings
            if "Exclusive Fullscreen Mode: Enable" in line or "Exclusive Fullscreen Mode: Automatic" in line:
                game_issues[f"**Risky Fullscreen settings detected. Consider setting it to `Prefer Borderless Fullscreen`.**"].append(f"L-{i}")

            # Critical issues
            if "Debug Console Mode: false" in line:
                debug_console_mode_off = True
                game_issues[f"**Debug Console Mode is off. Why?** Use `!mem`"].append(f"L-{i}")
            if 'Selected config: mode=custom config, path=""' in line:
                critical_issues[f"**Custom config not found**. Use `!rpcs3`"].append(f"L-{i}")
            if "log: Could not open port" in line:
                critical_issues[f"**MIDI device failed**. Close out any other programs using MIDI or restart computer."].append(f"L-{i}")
            if re.search(r"Driver Wake-Up Delay is too low. Use `!ddw`. (Yours is on \d+)", line):
                delay_value = int(re.search(r"\d+", line).group())
                if delay_value < 20:
                    critical_issues[f"**Driver Wake-Up Delay is too low. Use `!ddw`. Yours is set to ({delay_value})"].append(f"L-{i}")
                elif delay_value % 20 != 0:
                    game_issues[f"**Driver Delay Wake-Up Settings isn't a multiple of 20**. Please fix it. Yours is at (value: {delay_value})"].append(f"L-{i}")
            if "Write Color Buffers: false" in line:
                critical_issues[f"**Write Color Buffers isn't on**. Check the guide at `!rpcs3`"].append(f"L-{i}")
            if "SYS: Missing Firmware" in line:
                critical_issues[f"**No firmware installed**. Check the guide at `!rpcs3`"].append(f"L-{i}")
            if "SPU Block Size: Giga" in line:
                critical_issues[f"**SPU Block Size is on Giga**. Set it back to Auto or Mega."].append(f"L-{i}")
            if any(buffer_setting in line for buffer_setting in ["Write Depth Buffer: true", "Read Color Buffers: true", "Read Depth Buffer: true"]):
                critical_issues[f"**You enabled the wrong buffer settings.** Disable them in the Advanced tab."].append(f"L-{i}")
            if "Network Status: Disconnected" in line:
                critical_issues[f"**Incorrect Network settings.** Use `!netset`"].append(f"L-{i}")
            if "Regular file, “/dev_hdd0/game/BLUS30463/USRDIR/dx_high_memory.dta”" in line:
                high_memory_detected = True
            if any(gpu_issue in line for gpu_issue in ["Physical device reports a low amount of allowed deferred descriptor updates", "Will use graphics queue instead"]):
                if "Graphics device notice" not in graphics_device_notifications:
                    graphics_device_notifications.add("**Graphics device issue!** Get a nerd to check this out.")
                    game_issues[f"**Graphics device issue!** Get a nerd to check this out."].append(f"L-{i}")
            if "Your GPU does not support" in line:
                critical_issues[f"**Graphics card below minimum requirements.**"].append(f"L-{i}")
            if "sys_usbd: Transfer Error" in line:
                critical_issues[f"**Usbd error.** Too many PS3 instruments or passthrough devices connected?"].append(f"L-{i}")
            if any(error in line for error in ["Thread terminated due to fatal error: Verification failed", "VM: Access violation reading location"]):
                critical_issues[f"**Crash detected.** Tell us what you were doing before crashing."].append(f"L-{i}")

        # Check for combined issues
        if high_memory_detected and debug_console_mode_off:
            critical_issues[f"dx_high_memory is installed but Debug Console is off! **YOUR GAME WILL CRASH!**"].append(f"L-{i}")

        # Non-default settings detection
        non_default_settings_keywords = [
            "PPU Decoder: Recompiler (LLVM)",
            "SPU Decoder: Recompiler (LLVM)",
            "Shader Mode: Async Shader Recompiler",
            "Resolution: 1280x720",
            "Accurate SPU DMA: false",
            "Accurate RSX reservation access: false",
            "SPU Profiler: false",
            "MFC Commands Shuffling Limit: 0",
            "XFloat Accuracy: Approximate",
            "PPU Fixup Vector NaN Values: false",
            "Clocks scale: 100",
            "Max CPU Preempt Count: 0",
            "Handle RSX Memory Tiling: false",
            "Strict Rendering Mode: false",
            "Disable Vertex Cache: false",
            "Disable On-Disk Shader Cache: false",
            "Force Hardware MSAA Resolve: false",
            "Shader Compiler Threads: 0",
            "Allow Host GPU Labels: false",
            "Asynchronous Texture Streaming 2: false",
            "Start Paused: false",
            "Suspend Emulation Savestate Mode: false",
            "Compatible Savestate Mode: false",
            "Pause emulation on RPCS3 focus loss: false",
            "Pause Emulation During Home Menu: false"
        ]
        
        # Check for non-default settings
        for keyword in non_default_settings_keywords:
            if not any(keyword in line for line in core_section_lines):
                non_default_settings.append(f"{keyword}")

    # Preparing the output
    output = ""

    if critical_issues:
        output += "## Critical :exclamation: :\n"
        for issue, lines in critical_issues.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"  {issue} (on {line_info})\n"

    if game_issues:
        output += "\n## Warning :warning: :\n"
        for issue, lines in game_issues.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"  {issue} (on {line_info})\n"

    if non_default_settings:
        output += "\n## Non-Default Settings Detected. Revert the following things:\n"
        for setting in non_default_settings:
            output += f"  {setting}\n"
    
    if not critical_issues and not game_issues and not non_default_settings:
        output += "## No issues found. That was a yummy log file."

    # Add emulator information
    output += f"\n\n**Specs:**\n**Version:** {emulator_info['version']}\n**CPU:** {emulator_info['cpu']}\n**GPU:** {emulator_info['gpu']}\n{emulator_info['os']}"

    if language_message:
        output += f"\n\n{language_message}"

    return output
