import re
from collections import defaultdict

def analyze_log_file(log_file_path):
    # Initialize variables
    custom_config_found = False
    last_core_index = -1
    critical_issues = defaultdict(list)
    game_issues = defaultdict(list)
    non_default_settings = defaultdict(list)
    firmware_detected = False
    firmware_version = None
    emulator_info = {"version": "", "cpu": "", "os": "", "gpu": ""}
    language_message = ""
    
    # Sets to track duplicate issues
    onedrive_issues = set()
    save_issues = set()
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
        return "**Yuck!** This isn't a log for Rock Band 3. Feed me something better, or boot the game first to generate a log."

    # Extract emulator information
    emulator_info["version"] = lines[0].strip() if lines else ""
    emulator_info["cpu"] = lines[1].strip() if len(lines) > 1 else ""
    emulator_info["os"] = lines[2].strip() if len(lines) > 2 else ""

    # Detect emulator version number and flag if in the range 16920-17034
    version_match = re.search(r"RPCS3 v0\.0\.\d+-(\d+)-[a-f0-9]+", emulator_info["version"])
    if version_match:
        version_number = int(version_match.group(1))
        if 16920 <= version_number <= 17034:
            critical_issues["- **The version you're on is prone to crashing!** Update your RPCS3 as soon as possible!"] \
                .append("L-1")  # Assuming the version is always on the first line

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
        critical_issues[f"- **Vulkan compatible GPU not found!** We can't really help you with this one."].append(f"L-{i}")

    # Check log for firmware version and language, with firmware first
    for line in lines:
        firmware_match = re.search(r"SYS: Firmware version: (\d+\.\d+)", line)
        if firmware_match:
            firmware_version = firmware_match.group(1)
            firmware_detected = True
            if float(firmware_version) < 4.88:
                game_issues[f"- **Outdated firmware.** You are on `{firmware_version}`. **Please update to the latest PS3 firmware!**"].append(f"L-{lines.index(line) + 1}")

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
        enable_upnp = False
        upnp_error_detected = False
        ipadd_found = False
        bindadd_found = False
        dns_found = False
        gocentral_found = False
        # Non-default stuff
        ppudef_found = False
        spudef_found = False
        shaderdef_found = False
        spudmadef_found = False
        rsxresdef_found = False
        spuprofdef_found = False
        mfcdef_found = False
        xfloatdef_found = False
        ppufixdef_found = False
        clocksdef_found = False
        maxcpudef_found = False
        rsxtiledef_found = False
        strictrenderdef_found = False
        disvercachedef_found = False
        disdiskshaderdef_found = False
        msaaresolvedef_found = False
        shaderthreadsdef_found = False
        gpulabelsdef_found = False
        asynchtexdef_found = False
        startpausedef_found = False
        pausefocusdef_found = False
        pausehomedef_found = False
        wrdbufdef_found = False
        rcbufdef_found = False
        rdbufdef_found = False

        # Check for specific conditions in the extracted section
        for i, line in enumerate(core_section_lines, start=last_core_index + 1):
            # Check for high memory
            if 'CELL_ENOENT, "/dev_hdd0/game/BLUS30463/USRDIR/dx_high_memory.dta"' in line:
                game_issues[f"- **High memory file is missing!** Check out !mem for more information."].append(f"L-{i}")

            # Frame limit settings
            if "Frame limit" in line:
                match = re.search(r"Frame limit:\s*(\d+|Auto|Off)", line, re.IGNORECASE)
                if match:
                    frame_value = match.group(1)
                    if frame_value not in ["Auto", "Off", "Display"]:
                        game_issues[f"- **Weird Framelimit settings.** Set it to `Auto`, `Off`, or `Display` in the GPU tab of RB3's Custom Configuration. Yours is on {frame_value}"].append(f"L-{i}")
                else:
                    game_issues[f"- **Weird framerate settings:** Unknown"].append(f"L-{i}")

            # OpenGL Detect
            if "Renderer: OpenGL" in line:
                game_issues[f"- **You're using OpenGL!** You should really be on Vulkan. Set this in the GPU tab of RB3's Custom Configuration."].append(f"L-{i}")

            # 1920x1080 Detect
            if "Resolution: 1920x1080" in line:
                critical_issues[f"- **Forcing Rock Band to run at 1920x1080 will cause crashes!** You should really set this back to 1280x720."].append(f"L-{i}")

            # OneDrive install detection
            if "OneDrive" in line:
                if "OneDrive install detected" not in onedrive_issues:
                    onedrive_issues.add("- **OneDrive detected!** Please move files to C:\\Games**")
                    critical_issues[f"- **OneDrive detected!** Please move files to C:\\Games"].append(f"L-{i}")

            # Busted save
            if "dev_hdd0/home/00000001/savedata/BLUS30463-AUTOSAVE/ (Already exists)" in line:
                if "Busted save detected" not in save_issues:
                    save_issues.add("- **Busted Save detected!** Move BLUS30463-AUTOSAVE out of savedata folder in dev_hdd0")
                    critical_issues[f"- **Busted Save detected!** Move BLUS30463-AUTOSAVE out dev_hdd0\\home\\00000001\\savedata"].append(f"L-{i}")

            # Vblank Rate
            if re.search(r"Vblank Rate: (\d+)", line):
                vblank_frequency  = int(re.search(r"\d+", line).group())
                if vblank_frequency < 60:
                    critical_issues[f"- **Vblank should not be below 60**. Set it back to at least 60 in the Advanced tab of RB3's Custom Configuration."].append(f"L-{i}")
                elif vblank_frequency > 60:
                    game_issues[f"- Playing on a Vblank above 60 may make pitch detection unreliable and online unstable. I hope you know what you're doing."].append(f"L-{i}")

            # High Audio Buffer Duration
            match = re.search(r"Desired Audio Buffer Duration: (\d+)", line)
            if match:
                buffer_duration = int(match.group(1))
                if buffer_duration >= 100:
                    game_issues[f"- **Audio Buffer is quite high.** Consider lowering it to 32 in the Audio tab of RB3's Custom Configuration. It's set to {buffer_duration} ms"].append(f"L-{i}")

            # Audio Broken
            if "cellAudio: Failed to open audio backend" in line:
                critical_issues[f"- **Audio device doesn't work!** Check to make you selected the proper audio device in the Audio tab of RB3's Custom Configuration."].append(f"L-{i}")

            # Fullscreen settings
            if "Exclusive Fullscreen Mode: Enable" in line or "Exclusive Fullscreen Mode: Automatic" in line:
                game_issues[f"- Depending on your graphics driver, **you may experience issues with the Automatic or Exclusive Fullscreen settings** when clicking in and out of RPCS3. Consider setting it to `Prefer Borderless Fullscreen` in the Advanced tab of RB3's Custom Configuration."].append(f"L-{i}")

            # PSF Broken
            if "PSF: Error loading PSF" in line:
                critical_issues[f"- **PARAM.SFO file is busted!** DLC will probably not load! Replace them with working ones."].append(f"L-{i}")

            if "Debug Console Mode: false" in line:
                debug_console_mode_off = True
                game_issues[f"- **Debug Console Mode is off. Why?** Use !mem"].append(f"L-{i}")
            if 'Selected config: mode=custom config, path=""' in line:
                critical_issues[f"- **Custom config not found**. Use !rpcs3"].append(f"L-{i}")
            if "log: Could not open port" in line:
                critical_issues[f"- **MIDI device failed**. Close out any other programs using MIDI or restart computer."].append(f"L-{i}")
            if re.search(r"- Driver Wake-Up Delay is too low. Use `!ddw`. (Yours is on \d+)", line):
                delay_value = int(re.search(r"\d+", line).group())
                if delay_value < 20:
                    critical_issues[f"- **Driver Wake-Up Delay is too low. Use `!ddw`. Yours is set to ({delay_value})"].append(f"L-{i}")
                elif delay_value % 20 != 0:
                    game_issues[f"- **Driver Delay Wake-Up Settings isn't a multiple of 20**. Please fix it using !ddw. Yours is at (value: {delay_value})"].append(f"L-{i}")
            if "Write Color Buffers: false" in line:
                critical_issues[f"- **Write Color Buffers isn't on**. Check the guide at !rpcs3"].append(f"L-{i}")
            if "SYS: Missing Firmware" in line:
                critical_issues[f"- **No firmware installed**. Check the guide at !rpcs3"].append(f"L-{i}")
            if "SPU Block Size: Giga" in line:
                critical_issues[f"- **SPU Block Size is on Giga, which is very unstable!** Set it back to Auto or Mega in the GPU tab of RB3's Custom Configuration."].append(f"L-{i}")
            if "Network Status: Disconnected" in line:
                critical_issues[f"- **Incorrect Network settings.** Use !netset"].append(f"L-{i}")
            if "Regular file, “/dev_hdd0/game/BLUS30463/USRDIR/dx_high_memory.dta”" in line:
                high_memory_detected = True
            if any(gpu_issue in line for gpu_issue in ["Physical device reports a low amount of allowed deferred descriptor updates", "Will use graphics queue instead"]):
                if "Graphics device notice" not in graphics_device_notifications:
                    graphics_device_notifications.add("- **Graphics device issue!** Get a nerd to check this out.")
                    game_issues[f"- **Graphics device issue!** Get a nerd to check this out."].append(f"L-{i}")
            if "Your GPU does not support" in line:
                critical_issues[f"- **Graphics card is missing features.**"].append(f"L-{i}")
            if "sys_usbd: Transfer Error" in line:
                critical_issues[f"- **Usbd error.** Too many PS3 instruments or passthrough devices connected?"].append(f"L-{i}")
            if any(error in line for error in ["Thread terminated due to fatal error: Verification failed", "VM: Access violation reading location"]):
                critical_issues[f"- **Crash detected.** Tell us what you were doing before crashing."].append(f"L-{i}")
            if "UPNP Enabled: true" in line:
                enable_upnp = True
            if "No UPNP device was found" in line:
                upnp_error_detected = True
            # IP address detection
            if "IP address: 0.0.0.0" in line:
                ipadd_found = True
            # Bind address detection
            if "Bind address: 0.0.0.0" in line:
                bindadd_found = True
            # DNS address detection
            if "DNS address: 8.8.8.8" in line:
                dns_found = True
            # GoCentral address detection
            if "IP swap list: rb3ps3live.hmxservices.com=45.33.44.103" in line:
                gocentral_found = True
            # Non-default settings detection
            if "PPU Decoder: Recompiler (LLVM)" in line:
                ppudef_found = True
            if "SPU Decoder: Recompiler (LLVM)" in line:
                spudef_found = True
            if "Shader Mode: Async Shader Recompiler" in line:
                shaderdef_found = True
            if "Accurate SPU DMA: false" in line:
                spudmadef_found = True
            if "Accurate RSX reservation access: false" in line:
                rsxresdef_found = True
            if "SPU Profiler: false" in line:
                spuprofdef_found = True
            if "MFC Commands Shuffling Limit: 0" in line:
                mfcdef_found = True
            if "XFloat Accuracy: Approximate" in line:
                xfloatdef_found = True
            if "PPU Fixup Vector NaN Values: false" in line:
                ppufixdef_found = True
            if "Clocks scale: 100" in line:
                clocksdef_found = True
            if "Max CPU Preempt Count: 0" in line:
                maxcpudef_found = True
            if "Handle RSX Memory Tiling: false" in line:
                rsxtiledef_found = True
            if "Strict Rendering Mode: false" in line:
                strictrenderdef_found = True
            if "Disable Vertex Cache: false" in line:
                disvercachedef_found = True
            if "Disable On-Disk Shader Cache: false" in line:
                disdiskshaderdef_found = True
            if "Write Depth Buffer: false" in line:
                wrdbufdef_found = True
            if "Read Color Buffers: false" in line:
                rcbufdef_found = True
            if "Read Depth Buffer: false" in line:
                rdbufdef_found = True
            if "Force Hardware MSAA Resolve: false" in line:
                msaaresolvedef_found = True
            if "Shader Compiler Threads: 0" in line:
                shaderthreadsdef_found = True
            if "Allow Host GPU Labels: false" in line:
                gpulabelsdef_found = True
            if "Asynchronous Texture Streaming 2: false" in line:
                asynchtexdef_found = True
            if "Start Paused: false" in line:
                startpausedef_found = True
            if "Pause emulation on RPCS3 focus loss: false" in line:
                pausefocusdef_found = True
            if "Pause Emulation During Home Menu: false" in line:
                pausehomedef_found = True

        if not gocentral_found:
            game_issues[f"- **You're not on GoCentral :(.** Why not join the fun? The guide at `!rpcs3` can walk you through this."].append(f"L-{i}")

        # Non-default settings log
        if not ppudef_found:
            non_default_settings[f"- **CPU tab:** Set `PPU Decoder` back to `Recompiler (LLVM)`."].append(f"L-{i}")
        if not spudef_found:
            non_default_settings[f"- **CPU tab:** Set `SPU Decoder` back to `Recompiler (LLVM)`."].append(f"L-{i}")
        if not maxcpudef_found:
            non_default_settings[f"- **CPU tab:** Set `Max Power Saving CPU-preemptions` back to `0`."].append(f"L-{i}")
        if not xfloatdef_found:
            non_default_settings[f"- **CPU tab:** Set `SPU XFloat Accuracy` back to `Approximate XFloat`."].append(f"L-{i}")
        if not shaderdef_found:
            non_default_settings[f"- **GPU tab:** Set `Shader Mode` back to `Async (multi threaded)`."].append(f"L-{i}")
        if not strictrenderdef_found:
            non_default_settings[f"- **GPU tab:** Disable `Strict Rendering Mode` under the `Additional Settings` section."].append(f"L-{i}")
        if not shaderthreadsdef_found:
            non_default_settings[f"- **GPU tab:** Set `Number of Shader Compiler Threads` back to `Auto`."].append(f"L-{i}")
        if not asynchtexdef_found:
            non_default_settings[f"- **GPU tab:** You have enabled `Asynchronous Texture Streaming` under the `Additional Settings`. Only do this if you have a newer GPU and MTRSX enabled for your CPU."].append(f"L-{i}")
        if not bindadd_found:
            non_default_settings[f"- **Network tab:** Unless you have a good reason, `Bind address` should be set to `0.0.0.0`"].append(f"L-{i}")
        if not dns_found:
            non_default_settings[f"- **Network tab:** Unless you have a good reason, `DNS` should be set to `8.8.8.8`"].append(f"L-{i}")
        if not spudmadef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Accurate SPU DMA` under the `Core` section."].append(f"L-{i}")
        if not rsxresdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Accurate RSX reservation access` under the `Core` section."].append(f"L-{i}")
        if not spuprofdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `SPU Profiler` under the `Core` section."].append(f"L-{i}")
        if not ppufixdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `PPU Fixup Vector NaN Values` under the `Core` section."].append(f"L-{i}")
        if not clocksdef_found:
            non_default_settings[f"- **Advanced tab:** Set `Clocks scale` back to `100%`."].append(f"L-{i}")
        if not wrdbufdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Write Depth Buffer` under the `GPU` section."].append(f"L-{i}")
        if not rcbufdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Read Color Buffers DMA` under the `GPU` section."].append(f"L-{i}")
        if not rdbufdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Read Depth Buffer` under the `GPU` section."].append(f"L-{i}")
        if not rsxtiledef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Handle RSX Memory Tiling` under the `GPU` section."].append(f"L-{i}")
        if not disvercachedef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Disable Vertex Cache` under the `GPU` section."].append(f"L-{i}")
        if not disdiskshaderdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Disable On-Disk Shader Cache` under the `GPU` section."].append(f"L-{i}")
        if not msaaresolvedef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Force Hardware MSAA Resolve` under the `GPU` section."].append(f"L-{i}")
        if not gpulabelsdef_found:
            non_default_settings[f"- **Advanced tab:** Disable `Allow Host GPU Labels (Experimental)` under the `GPU` section."].append(f"L-{i}")
        if not startpausedef_found:
            non_default_settings[f"- **Emulator tab:** Disable `Pause emulation after loading savestates` under the `Emulator Settings` section."].append(f"L-{i}")
        if not pausefocusdef_found:
            non_default_settings[f"- **Emulator tab:** You enabled `Pause emulation on RPCS3 focus loss` under the `Emulator Settings` section. This makes your emulator pause whenever you click out of it. Are you sure about this?"].append(f"L-{i}")
        if not pausehomedef_found:
            non_default_settings[f"- **Emulator tab:** You enabled `Pause emulation during home menu` under the `Emulator Settings` section. This makes your emulator pause whenever you bring up the home menu. Are you sure about this?"].append(f"L-{i}")
        if not ipadd_found:
            non_default_settings[f"- You have somehow changed the `IP address` in the config file. Unless you have a good reason, set it back to `0.0.0.0`"].append(f"L-{i}")
        if not mfcdef_found:
            non_default_settings[f"- You changed `MFC Commands Shuffling Limit` in the config file for RB3. Why? Set it back."].append(f"L-{i}")

        # Check for combined issues
        if high_memory_detected and debug_console_mode_off:
            critical_issues[f"- **dx_high_memory is installed but Debug Console is off! YOUR GAME WILL CRASH!**"].append(f"L-{i}")

        if enable_upnp and upnp_error_detected:
            critical_issues[f"- **UPNP error detected! You will probably crash while online!**"].append(f"L-{i}")

    # Preparing the output
    output = ""

    if critical_issues:
        output += "## Critical :exclamation:\n_Guaranteed to be a problem!_\n"
        for issue, lines in critical_issues.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"{issue} (on {line_info})\n"

    if game_issues:
        output += "\n## Warning :warning:\n_May or may not cause issues._\n"
        for issue, lines in game_issues.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"{issue} (on {line_info})\n"

    if non_default_settings:
        output += "\n## Non-default settings :question:\n_Set these in Rock Band 3's Custom Configuration. Use `!global` for more information._\n"
        for issue, lines in non_default_settings.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"{issue} (on {line_info})\n"
    
    if not critical_issues and not game_issues and not non_default_settings:
        output += "## No issues detected. Let us know if this is wrong."

    # Add emulator information
    output += f"\n\n**Version:** {emulator_info['version']}\n**CPU:** {emulator_info['cpu']}\n**GPU:** {emulator_info['gpu']}\n{emulator_info['os']}"

    if language_message:
        output += f"\n\n{language_message}"

    return output
