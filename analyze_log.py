import re
from collections import defaultdict

def analyze_log_file(log_file_path):
    # Initialize variables
    custom_config_found = False
    last_core_index = -1
    critical_issues = defaultdict(list)
    game_issues = defaultdict(list)
    non_default_settings = defaultdict(list)
    pad_info = defaultdict(list)
    pad_issues = defaultdict(list)
    firmware_detected = False
    firmware_version = None
    local_build_detected = False
    emulator_info = {"version": "", "cpu": "", "os": "", "gpu": ""}
    vulkangpu = False
    language_message = ""
    call_stack = []
    thread_context = []
    # Sets to track duplicate issues
    onedrive_install = set()
    programfiles_install = set()
    save_issues = set()
    graphics_device_notifications = set()

    # Attempt to open and read the log file with different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252']  # Add more encodings if needed
    lines = []

    for encoding in encodings:
        try:
            with open(log_file_path, 'r', encoding=encoding) as file:
                # Read and normalize all lines in one go
                lines = [line.replace("“", '"')
                             .replace("”", '"')
                             .replace("‘", "'")
                             .replace("’", "'") for line in file.readlines()]
                
                # Collect the entire call-stack block
                call_stack_block = []
                in_stack = False
                for line in lines:
                    # start when we hit the call‐stack header
                    if line.strip().startswith("Call stack:"):
                        in_stack = True
                    if in_stack:
                        # stop only when we hit a truly empty line *after* we've started collecting
                        if line.lstrip().startswith("·"):
                           break
                        call_stack_block.append(line.rstrip())

                # Collect thread context block
                in_context = False
                for line in lines:
                    low = line.lower()
                    # start when we hit the context header
                    if "thread context:" in low:
                        in_context = True
            
                    if in_context:
                        # once we reach the call‐stack marker, stop collecting
                        if low.startswith("call stack:"):
                            break
                        # otherwise grab every single line (including blanks)
                        thread_context.append(line.rstrip())
            break  # Exit loop if successful
        except UnicodeDecodeError:
            continue  # Try next encoding
    else:
        return "**Error**: Unable to read the log file with the provided encodings."

    # Check if this is a Rock Band 3 log
    if not any("SYS: Title: Rock Band 3" in line for line in lines) or \
       not any("SYS: Serial: BLUS30463" in line for line in lines):
        return "**I don't understand this!** Boot the game first to generate a log."

    # Extract emulator information
    emulator_info["version"] = lines[0].strip() if lines else ""
    emulator_info["cpu"] = lines[2].strip() if len(lines) > 2 else ""
    emulator_info["os"] = lines[3].strip() if len(lines) > 3 else ""

    # Check for GPU information
    for i, line in enumerate(lines):
        if "CFG: Setting the default renderer to Vulkan. Default GPU:" in line:
            gpu_match = re.search(r"Default GPU: '(.*)'", line)
            gpu = gpu_match.group(1)
            emulator_info["gpu"] = gpu
            if gpu != "Intel(R) Iris(R) Xe Graphics":
                vulkangpu = True
    
    

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

        if "Language: Portuguese (Portugal)" in line:
            language_message = "Ola. Explique o que aconteceu. / This user speaks Portuguese."

        # Check if it's a weird fork
        if "this is a local build" in line:
            local_build_detected = True

    # Scan the log file for "Used configuration" and track indices
    for i, line in enumerate(lines):
        if "Applying custom config" in line:
            custom_config_found = True
        if "Used configuration" in line:
            last_core_index = i
    if not custom_config_found:
        critical_issues[f"- **You have no custom configuration set!** Please follow the guide at `!rpcs3`."].append(f"L-{i}")
    
    # Process log information if custom config was found
    if custom_config_found and last_core_index != -1:
        core_section_lines = lines[last_core_index:]

        # Save these for later
        high_memory_detected = False
        debugconsole_off = False
        enable_upnp = False
        wehavecrashed = False
        upnp_error = False
        gooddns = False
        gocentral_found = False
        vsyncoff_found = False
        openglrenderer = False
        vblankabove60 = False
        fastfifo = False
        ddunotzero = False
        ddutoolow = False
        ddunotmult = False
        netoffline = False
        psnoffline = False
        sussydlc = False

        # Non-default stuff
        defaultipaddress = False
        defaultbindaddress = False
        ppudefault = False
        spudefault = False
        shaderlegacy = False
        accuratespudma = True
        accuratersxreserve = True
        spuprofiler = True
        mfccommandsdefault = False
        xfloatapprox = False
        #ppufixdef_found = False
        clocksscaledefault = False
        cpupowersavedefault = False
        multirsx = True
        handlersxmemorytile = False
        strictrendering = True
        vertexcache = True
        diskshadercache = True
        hardwaremsaa = True
        compilerthreadsdefault = False
        hostgpulabels = True
        asynctexture = True
        pausesavestate = True
        pausefocusloss = True
        pauseonhome = True
        writedepthbuf = True
        colorbuffdma = True
        readdepthbuff = True

        # Check for specific conditions in the extracted section
        for i, line in enumerate(core_section_lines, start=last_core_index + 1):
            # Check for high memory
            if 'CELL_ENOENT, "/dev_hdd0/game/BLUS30463/USRDIR/dx_high_memory.dta"' in line:
                critical_issues[f"- **High memory file is missing!** Use `!mem` for more info."].append(f"L-{i}")

            #Frame limit
            if "Frame limit: Infinite" in line or "Frame limit: 50" in line or "Frame limit: 30" in line or "Frame limit: PS3 Native" in line:
                critical_issues[f"- **You are using an unsupported `Framelimit` value!** Set this back to `60`, `120, `Display`, or `Off` under the `GPU` tab in RB3's Custom Configuration."].append(f"L-{i}")

            # 1920x1080 Detect
            if "Resolution: 1920x1080" in line:
                critical_issues[f"- **Forcing Rock Band to run at 1920x1080 will cause crashes!** You should really set this back to 1280x720 under the `GPU` tab in RB3's Custom Configuration."].append(f"L-{i}")

            # OneDrive install detection
            if "OneDrive" in line:
                if "OneDrive install detected" not in onedrive_install:
                    onedrive_install.add("- **OneDrive detected! This can lead to corrupted files and saves!** Please move files to `C:\\Games`**")
                    critical_issues[f"- **OneDrive detected! This can lead to corrupted files and saves!** Please move files to `C:\\Games`"].append(f"L-{i}")

            # Program Files install detection
            if "C:\\Program Files" in line:
                if "Program Files install detected" not in programfiles_install:
                    programfiles_install.add("- **Program Files install detected! This can lead to issues due to permissions!** Please move files to `C:\\Games`**")
                    critical_issues[f"- **Program Files install detected! This can lead to issues due to permissions!** Please move files to `C:\\Games`."].append(f"L-{i}")

            # Busted save
            if "dev_hdd0/home/00000001/savedata/BLUS30463-AUTOSAVE/ (Already exists)" in line:
                if "Busted save detected" not in save_issues:
                    save_issues.add("- **Busted save detected!** Move the `BLUS30463-AUTOSAVE`folder out of savedata folder in `dev_hdd0`.")
                    critical_issues[f"- **Busted save detected!** Move the `BLUS30463-AUTOSAVE` folder out of `dev_hdd0\\home\\00000001\\savedata`."].append(f"L-{i}")

            # Vblank Rate
            if re.search(r"Vblank Rate: (\d+)", line):
                vblank_frequency  = int(re.search(r"\d+", line).group())
                if vblank_frequency < 60:
                    critical_issues[f"- **VBlank should not be below `60`**. Set it back to 60 under the `Advanced` tab in RB3's Custom Configuration."].append(f"L-{i}")
                elif vblank_frequency > 60:
                    vblankabove60 = True
                    game_issues[f"- Increasing VBlank for a higher frame rate is **NOT** recommended. Set it back to `60` under the `Advanced` tab in RB3's Custom Configuration and type in `!vsyncmeta` for more info."].append(f"L-{i}")


            # VSync is off
            if "VSync: false" in line:
                vsyncoff_found = True

            # OpenGL renderer
            if "Renderer: OpenGL" in line:
                openglrenderer = True

            # High Audio Buffer Duration
            match = re.search(r"Desired Audio Buffer Duration: (\d+)", line)
            if match:
                buffer_duration = int(match.group(1))
                if buffer_duration >= 100:
                    game_issues[f"- **Audio Buffer is quite high.** Yours is set to `{buffer_duration}` ms. Consider lowering it to at least `32` ms under the `Audio` tab in RB3's Custom Configuration."].append(f"L-{i}")
            
            if (
                "/dev_hdd0/game/BLUS30463/USRDIR/HMX0" in line
                and "/dev_hdd0/game/BLUS30463/USRDIR/HMX0756" not in line
            ):
                sussydlc = True
            
            if (
                "/dev_hdd0/game/BLUS30050/USRDIR/CCF0" in line
                and "/dev_hdd0/game/BLUS30050/USRDIR/CCF0099" not in line
            ):
                sussydlc = True

            # Audio Broken
            if "cellAudio: Failed to open audio backend" in line or "Thread terminated due to fatal error: Unsupported layout" in line:
                critical_issues[f"- **Audio device doesn't work!** Check to make you selected the proper audio device and format under the `Audio` tab in RB3's Custom Configuration."].append(f"L-{i}")

            # PTBR doesn't work
            if "Language: Portuguese (Brazil)" in line:
                game_issues[f"- Devido a um bug no RPCS3, a tradução para português brasileiro não funcionará com o idioma definido em `Português (Brasil)` por enquanto. Altere para `Português (Portugal)` na aba `Sistema` das configurações personalizadas do RB3."].append(f"L-{i}")

            # Fullscreen settings
            if "Exclusive Fullscreen Mode: Enable" in line or "Exclusive Fullscreen Mode: Automatic" in line:
                game_issues[f"- Depending on your graphics driver, **you may experience issues with the Automatic or Exclusive Fullscreen settings** when clicking in and out of RPCS3. Consider setting it to `Prefer Borderless Fullscreen` under the `Advanced` tab in RB3's Custom Configuration."].append(f"L-{i}")

            # Shader Compilation Broke
            if "Shader does not write to any output register and will be NOPed" in line:
                critical_issues[f"- **Shader compilation failed!** Clear the cache and update RPCS3 if you haven't. Use `!caches` for more info."].append(f"L-{i}")

            # Vulkan Device Lost
            if "Driver crashed with unspecified error or stopped responding and recovered" in line:
                critical_issues[f"- **Display error!** Check your graphics card drivers. Use `!vkdiag` for more info."].append(f"L-{i}")

            # PSF Broken
            if "PSF: Error loading PSF" in line:
                critical_issues[f"- **PARAM.SFO file is busted!** DLC will probably not load! Replace them with working ones by installing the vanilla updates. Try typing in `!BLUS30050`, `!BLUS30147`, and `!BLUS30463` for downloads."].append(f"L-{i}")
            
            # MBox=empty
            if "MBox=empty" in line:
                critical_issues[f"- **Weird MBox empty error!** You have run into a freak accident. Please tell us how this happened."].append(f"L-{i}")
            
            # Debug Console
            if "Debug Console Mode: false" in line:
                debugconsole_off = True
                critical_issues[f"- **Debug Console Mode is off!** You will run into memory issues! Use `!mem` for more info."].append(f"L-{i}")
            
            # Configuration not found
            if 'Selected config: mode=custom config, path=""' in line:
                critical_issues[f"- **Custom config not found**. Follow the guide at `!rpcs3` to get setup properly."].append(f"L-{i}")
            
            # Using Fast FIFO
            if "RSX FIFO Fetch Accuracy: Fast" in line:
                fastfifo = True
            
            # Driver Wake-Up Delay
            if re.search(r"Driver Wake-Up Delay: (\d+)", line):
                delay_value = int(re.search(r"\d+", line).group())
                if delay_value < 0:
                    ddunotzero = True
                elif delay_value < 20:
                    ddutoolow = True
                elif delay_value % 20 != 0:
                    ddunotmult = True
            
            # WCB
            if "Write Color Buffers: false" in line:
                critical_issues[f"- **Write Color Buffers isn't on**. Use `!wcb` for more info."].append(f"L-{i}")
            
            # Atomic & Ordered
            if 'RSX FIFO Fetch Accuracy: "Ordered & Atomic"' in line:
                non_default_settings[f"- **You don't need to use `Ordered & Atomic`**. This usually runs worse. Set it back to `Fast` or `Atomic` under the `Advanced` tab in RB3's Custom Configuration."].append(f"L-{i}")
            
            # Firmware missing
            if "SYS: Missing Firmware" in line:
                critical_issues[f"- **No firmware installed**. Follow the guide at `!rpcs3` to get setup properly."].append(f"L-{i}")
            
            # SPU Block Size Giga
            if "SPU Block Size: Giga" in line:
                critical_issues[f"- **`SPU Block Size` is on `Giga`, which is very unstable!** Set it back to `Auto` or `Mega` under the `CPU` tab in RB3's Custom Configuration."].append(f"L-{i}")

            # Relaxed XFloat:
            if "SPU XFloat Accuracy: Relaxed" in line:
                critical_issues[f"- **`SPU XFloat Accuracy` is on `Relaxed`, which will break some modes, like practice!** Set it back to `Approximate` under the `CPU` tab in RB3's Custom Configuration."].append(f"L-{i}")

            # Network Status
            if "Internet enabled: Disconnected" in line:
                netoffline = False

            # PSN
            if "PSN status: Disconnected" in line:
                psnoffline = False

            # High Memory file
            if "Regular file, “/dev_hdd0/game/BLUS30463/USRDIR/dx_high_memory.dta”" in line:
                high_memory_detected = True
            
            # GPU does not feature
            if "Your GPU does not support" in line:
                game_issues[f"- RPCS3 is reporting that your GPU is missing features. This may or may not affect Rock Band 3."].append(f"L-{i}")
            
            ## Common crashes ##
            # Hard crash
            if any(error in line for error in ["Thread terminated due to fatal error: Verification failed", "VM: Access violation reading location"]):
                wehavecrashed = True
            
            # Bad dump
            #if "r1 : 0xd00203f0 ->" in line:
                #critical_issues[f"- **You probably have a bad dump!** Get some fresh meats from `!arbys`."].append(f"L-{i}")
            # Presence Crash
            if "{\\qPlaylist\\q:\\q,\\qSubPlaylist\\" in line:
                critical_issues[f"- **Error writing to Presence file!** You'll need to delete all files called `currentsong` along with `discordrp.json` in RB3's `USRDIR` folder. Use `!gamedata` for more info."].append(f"L-{i}")

            # Prefab edit crash
            if "0x003cdcf4 (0x0) called" in line:
                critical_issues[f"- **You tried to edit a custom character!** Please don't do this."].append(f"L-{i}")

            # Synth setting
            if "0x001c8eac (0x0) called" in line:
                critical_issues[f"- **You've crashed due to RB3DX's synth option.** Please disable it under Audio & SFX in Deluxe Settings."].append(f"L-{i}")

            # Bad song DTA: Bad channel layout
            if "0x0055b204 (0x0) called" in line:
                critical_issues[f"- **Bad song DTA!** You tried to play a song with incorrect audio channel mapping. Report the issue to the author."].append(f"L-{i}")
            
            # Bad song DTA: Schizo part definitions
            if "0x00580b48 (0x0) called" in line:
                critical_issues[f"- **Bad song DTA!** You tried to play a song that says it has a part it really doesn't. Report the issue to the author."].append(f"L-{i}")
            
            # Hanging
            if "Emulation has been frozen! You can either use debugger tools to inspect current emulation state or terminate it" in line:
                wehavecrashed = True
            
            ## Pad Stuff ##
            # Pad profile in use
            if 'Product ID: 528' in line:
                pad_issues[f"- **Drums have the wrong Device Class**! All Rock Band Drums need need to be set to `Rock Band Pro`."].append(f"L-{i}")
            
            # Pad profile in use
            if 'input_configs/BLUS30463/Default.yml' in line:
                pad_issues[f"- **Per-game pad profile detected**! We heavily discourage this. Check `!padprofiles`."].append(f"L-{i}")
            
            # Mic in use
            if 'cellMic: cellMicOpenEx(dev_nu' in line:
                pad_info[f"- At least one microphone is set up in I/O."].append(f"L-{i}")
            
            # Passthrough RB Guitar
            if 'matches up with LDD <RockBandGuitar>' in line:
                pad_info[f"- At least one Rock Band guitar is connected with passthrough."].append(f"L-{i}")
            
            # Santroller device in use
            if 'sys_usbd: Found device: Santroller' in line:
                pad_info[f"- I see a Santroller device. All hail Sanjay."].append(f"L-{i}")
            
            # I/O MIDI Keyboard in use
            if 'Emulated Midi Pro Adapter (type=Keyboard' in line:
                pad_info[f"- A MIDI keyboard is set up via I/O."].append(f"L-{i}")
            
            # Passthrough RB Keytar
            if 'matches up with LDD <RockBandKeyboard>' in line:
                pad_info[f"- The game should see Rock Band Keyboard connected."].append(f"L-{i}")
            
            # I/O MIDI Drums in use
            if 'Emulated Midi Pro Adapter (type=Drums' in line:
                pad_info[f"- A MIDI Drum Kit is set up via I/O."].append(f"L-{i}")
            
            # Passthrough RB drums
            if 'matches up with LDD <RockBandDrums>' in line:
                pad_info[f"- The game should see Rock Band drums connected."].append(f"L-{i}")
            
            # I/O MIDI Protar 17 in use
            if 'Emulated Midi Pro Adapter (type=Guitar (17 frets)' in line:
                pad_info[f"- A 17 fret Pro Guitar is set up via I/O."].append(f"L-{i}")
            
            # Passthrough RB Mustang
            if 'matches up with LDD <RockBandButtonGuitar>' in line:
                pad_info[f"- The game should see a Rock Band Mustang Pro Guitar connected."].append(f"L-{i}")
            
            # I/O MIDI Protar 22 in use
            if 'Emulated Midi Pro Adapter (type=Guitar (22 frets)' in line:
                pad_info[f"- A 22 fret Pro Guitar is set up via I/O."].append(f"L-{i}")
            
            # Passthrough RB Squier
            if 'matches up with LDD <RockBandRealGuitar>' in line:
                pad_info[f"- The game should see a Rock Band Squier Pro Guitar connected."].append(f"L-{i}")
            
            # USB overload
            if "sys_usbd: Transfer Error" in line:
                critical_issues[f"- **Usbd error.** This shouldn't be happening anymore! Tell us how your USB devices are connected."].append(f"L-{i}")
            
            # Mic error
            if 'Make sure microphone use is authorized under' in line:
                critical_issues[f"- **The emulator can't use your microphone!** Does RPCS3 have permission to use your mic? Is something else using it?"].append(f"L-{i}")
            
            # MIDI error
            if "log: Could not open port" in line:
                critical_issues[f"- **Can't hook into MIDI device!** Close out any other programs using MIDI or restart computer."].append(f"L-{i}")
            
            ## Network stuff ##
            # User is stuck online
            if "User is already logged in" in line:
                critical_issues[f"- **Zombie RPCN login!** You lost connection to RPCN and it did not log out correctly. Wait around 20 minutes before trying again. If you're using a VPN, try without."].append(f"L-{i}")
            
            # Check if UPNP is on
            if "UPNP Enabled: true" in line:
                enable_upnp = True
            
            # UPNP Died
            if "No UPNP device was found" in line:
                upnp_error = True
            
            # IP address detection
            if "IP address: 0.0.0.0" in line:
                defaultipaddress = True
            
            # Bind address detection
            if "Bind address: 0.0.0.0" in line:
                defaultbindaddress = True
            
            # DNS address detection
            if "DNS address: 8.8.8.8" or "DNS address: 1.1.1.1" or "45.33.44.103" in line:
                gooddns = True

            if "45.33.44.103" in line:
                gocentral_found = True
            
            # GoCentral address detection
            if "IP swap list: rb3ps3live.hmxservices.com=45.33.44.103" in line:
                gocentral_found = True
            
            ## Non-default settings spaghetti ##
            if "PPU Decoder: Recompiler (LLVM)" in line:
                ppudefault = True
            if "SPU Decoder: Recompiler (LLVM)" in line:
                spudefault = True
            if "Shader Mode: Legacy Recompiler" in line:
                shaderlegacy = True
            if "Accurate SPU DMA: false" in line:
                accuratespudma = False
            if "Accurate RSX reservation access: false" in line:
                accuratersxreserve = False
            if "SPU Profiler: false" in line:
                spuprofiler = False
            if "MFC Commands Shuffling Limit: 0" in line:
                mfccommandsdefault = True
            if "XFloat Accuracy: Approximate" in line:
                xfloatapprox = True
            if "Clocks scale: 100" in line:
                clocksscaledefault = True
            if "Max CPU Preempt Count: 0" in line:
                cpupowersavedefault = True
            if "Strict Rendering Mode: false" in line:
                strictrendering = False
            if "Multithreaded RSX: false" in line:
                multirsx = False
            if "Handle RSX Memory Tiling: false" in line:
                handlersxmemorytile = False
            if "Disable Vertex Cache: false" in line:
                vertexcache = True
            if "Disable On-Disk Shader Cache: false" in line:
                diskshadercache = True
            if "Write Depth Buffer: false" in line:
                writedepthbuf = False
            if "Read Color Buffers: false" in line:
                colorbuffdma = False
            if "Read Depth Buffer: false" in line:
                readdepthbuff = False
            if "Force Hardware MSAA Resolve: false" in line:
                hardwaremsaa = False
            if "Shader Compiler Threads: 0" in line:
                compilerthreadsdefault = True
            if "Allow Host GPU Labels: false" in line:
                hostgpulabels = False
            if "Asynchronous Texture Streaming 2: false" in line:
                asynctexture = False
            if "Start Paused: false" in line:
                pausesavestate = False
            if "Pause emulation on RPCS3 focus loss: false" in line:
                pausefocusloss = False
            if "Pause Emulation During Home Menu: false" in line:
                pauseonhome = False

        if not ppudefault:
            non_default_settings[f"- **CPU tab:** Set `PPU Decoder` back to `Recompiler (LLVM)`."].append(f"L-{i}")
        if not spudefault:
            non_default_settings[f"- **CPU tab:** Set `SPU Decoder` back to `Recompiler (LLVM)`."].append(f"L-{i}")
        if shaderlegacy:
            non_default_settings[f"- **GPU tab:** Set `Shader Mode` back to `Async Recompiler (multi-threaded)` or `Async Recompiler with Shader Interpreter`."].append(f"L-{i}")
        if accuratespudma:
            non_default_settings[f"- **Advanced tab:** Disable `Accurate SPU DMA` under the `Core` section."].append(f"L-{i}")
        if not defaultipaddress:
            non_default_settings[f"- You have somehow changed the `IP address` in the config file. Unless you have a good reason, set it back to `0.0.0.0`"].append(f"L-{i}")
        if not defaultbindaddress:
            non_default_settings[f"- **Network tab:** Unless you have a good reason, `Bind address` should be set to `0.0.0.0`"].append(f"L-{i}")
        if accuratersxreserve:
            non_default_settings[f"- **Advanced tab:** Disable `Accurate RSX reservation access` under the `Core` section."].append(f"L-{i}")
        if spuprofiler:
            non_default_settings[f"- **Advanced tab:** Disable `SPU Profiler` under the `Core` section."].append(f"L-{i}")
        if not mfccommandsdefault:
            non_default_settings[f"- You changed `MFC Commands Shuffling Limit` in the config file for RB3. _Why?_ Set it back."].append(f"L-{i}")
        if not xfloatapprox:
            non_default_settings[f"- **CPU tab:** Set `SPU XFloat Accuracy` back to `Approximate XFloat`."].append(f"L-{i}")
        if not clocksscaledefault:
            non_default_settings[f"- **Advanced tab:** Set `Clocks scale` back to `100%`."].append(f"L-{i}")
        if not cpupowersavedefault:
            non_default_settings[f"- **CPU tab:** Set `Max Power Saving CPU-preemptions` back to `0`."].append(f"L-{i}")
        if strictrendering:
            non_default_settings[f"- **GPU tab:** Disable `Strict Rendering Mode` under the `Additional Settings` section."].append(f"L-{i}")
        if handlersxmemorytile:
            non_default_settings[f"- **Advanced tab:** Disable `Handle RSX Memory Tiling` under the `Advanced` section."].append(f"L-{i}")
        if not vertexcache:
            non_default_settings[f"- **Advanced tab:** Disable `Disable Vertex Cache` under the `GPU` section."].append(f"L-{i}")
        if not diskshadercache:
            non_default_settings[f"- **Advanced tab:** Disable `Disable On-Disk Shader Cache` under the `GPU` section."].append(f"L-{i}")
        if writedepthbuf:
            non_default_settings[f"- **Advanced tab:** Disable `Write Depth Buffer` under the `GPU` section."].append(f"L-{i}")
        if colorbuffdma:
            non_default_settings[f"- **Advanced tab:** Disable `Read Color Buffers DMA` under the `GPU` section."].append(f"L-{i}")
        if readdepthbuff:
            non_default_settings[f"- **Advanced tab:** Disable `Read Depth Buffer` under the `GPU` section."].append(f"L-{i}")
        if hardwaremsaa:
            non_default_settings[f"- **Advanced tab:** Disable `Force Hardware MSAA Resolve` under the `GPU` section."].append(f"L-{i}")
        if not compilerthreadsdefault:
            non_default_settings[f"- **GPU tab:** Set `Number of Shader Compiler Threads` back to `Auto`."].append(f"L-{i}")
        if hostgpulabels:
            non_default_settings[f"- **Advanced tab:** Disable `Allow Host GPU Labels (Experimental)` under the `GPU` section."].append(f"L-{i}")
        if asynctexture and not multirsx:
            non_default_settings[f"- **GPU tab:** You have enabled `Asynchronous Texture Streaming` under the `Additional Settings` yet didn't enable `Multithreaded RSX` under the `GPU` tab in RB3's Custom Configuration. _Why?_"].append(f"L-{i}")
        if asynctexture and multirsx:
            non_default_settings[f"- **GPU tab:** You have enabled `Asynchronous Texture Streaming` under the `Additional Settings` along with Multithreaded RSX` under the `GPU` tab in RB3's Custom Configuration. Only do this if you have plenty of CPU cores!"].append(f"L-{i}")
        if pausesavestate:
            non_default_settings[f"- **Emulator tab:** Disable `Pause emulation after loading savestates` under the `Emulator Settings` section."].append(f"L-{i}")
        if pausefocusloss:
            non_default_settings[f"- **Emulator tab:** You enabled `Pause emulation on RPCS3 focus loss` under the `Emulator Settings` section. This freezes emulation whenever you click out of it. Are you sure about this?"].append(f"L-{i}")
        if pauseonhome:
            non_default_settings[f"- **Emulator tab:** You enabled `Pause emulation during home menu` under the `Emulator Settings` section. This freezes emulation whenever you bring up the home menu. Are you sure about this?"].append(f"L-{i}")
        ## Additional Stuff ##
        # Bad build
        if local_build_detected:
            critical_issues[f"- **This is not an official RPCS3 build!** We do not provide support for these builds nor does the RPCS3 Discord server. Please [[download an official version of RPCS3 from their website]](https://rpcs3.net/download)."].append(f"L-{i}")
        # Bad DLC
        if sussydlc:
            game_issues[f"- **Where did you get your DLC?** It might be causing issues. You installed ""HMX"" format DLC incorrectly."].append(f"L-{i}")
        
        # Crashed
        if wehavecrashed:
            critical_issues[f"- **Crash detected.** Tell us what you were doing before crashing."].append(f"L-{i}")
        
        # User isn't on GoCentral
        if not gocentral_found:
            game_issues[f"- **You're not on GoCentral :(.** Why not join the fun? The guide at `!rpcn` can walk you through this."].append(f"L-{i}")

        ## Combos ##
        # High mem without debug file
        if high_memory_detected and debugconsole_off:
            critical_issues[f"- **dx_high_memory is installed but Debug Console is off! YOUR GAME WILL CRASH!** Use `!mem` for more info."].append(f"L-{i}")

        # UPNP fail
        if enable_upnp and upnp_error:
            critical_issues[f"- **UPNP error detected! You will probably crash while online!** You will have to manually port forward. Use `!ports` for more info."].append(f"L-{i}")

        # [no bitches image] No Vulkan??
        if not vulkangpu and not openglrenderer:
            critical_issues[f"- **This computer cannot use Vulkan!** Please set the renderer to `OpenGL` under the `GPU` tab in RB3's Custom Configuration."].append(f"L-{i}")

        # Forced to the OpenGL mines
        if not vulkangpu and openglrenderer:
            game_issues[f"- You are correctly on OpenGL, as your graphics device is incapable of Vulkan."].append(f"L-{i}")

        # User is using OpenGL for no reason basically
        if vulkangpu and openglrenderer:
            critical_issues[f"- **You're using OpenGL!** Unless you're on a very low end system, you should really using Vulkan. You can change this under the `GPU` tab in RB3's Custom Configuration."].append(f"L-{i}")
        
        # VSync Meta suggestion
        if vsyncoff_found and vblankabove60:
            game_issues[f"- **It could be better!** You may get a smoother experience with the new VSync meta. Use `!vsyncmeta` for more info."].append(f"L-{i}")
        
        # IP is there but it's still offline   
        if netoffline or psnoffline and gocentral_found:
            game_issues[f"- You've added the GoCentral address but have set RPCS3 to be offline under the `Network` tab in RB3's Custom Configuration. Use `!rpcn` for more info."].append(f"L-{i}")
        
        # DDU above 0 but user is using Atomic
        if not fastfifo and not ddunotzero:
            game_issues[f"- You've set `Driver Wake-Up Delay` above `0` even though you set `RSX FIFO Accuracy` to `Atomic`. As far as we know, this isn't necessary. You can change this under the `Advanced` tab in RB3's Custom Configuration."].append(f"L-{i}")

        # FAST: FIFO too low
        if fastfifo and ddutoolow:
            critical_issues[f"- **`Driver Wake-Up Delay` is too low.** Yours is set to `{delay_value}`. Use `!dwd`."].append(f"L-{i}")
        
        #FAST: FIFO not 20 mult
        if fastfifo and ddunotmult:
            critical_issues[f"- **`Driver Wake-Up Delay` isn't a multiple of 20**. Yours is at `{delay_value}`. Use `!dwd`."].append(f"L-{i}")

    ## Output ##
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
        output += "\n## Non-default settings :question:\n_Change these in Rock Band 3's Custom Configuration. Use `!global` for more information._\n"
        for issue, lines in non_default_settings.items():
            output += f"{issue}\n"

    if pad_issues:
        output += "\n## Input Errors :guitar:\n_Here's some problems with your controllers._\n"
        for issue, lines in pad_issues.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"{issue} (on {line_info})\n"

    details = []
    if thread_context:
        details.append("=== THREAD CONTEXT ===")
        details.extend(thread_context)
        details.append("")  # blank line
    if call_stack_block:
        details.append("=== CALL STACK + DISASSEMBLY ===")
        details.extend(call_stack_block)

    diagnostics_file = None
    if details:
        diagnostics_file = log_file_path + ".debug.txt"
        with open(diagnostics_file, "w", encoding="utf-8") as f:
            f.write("\n".join(details))
    
    if not critical_issues and not game_issues and not non_default_settings and not pad_issues:
        output += "## No issues detected. Either nothing is wrong or I don't know how to detect your issue yet."
    
    if pad_info:
        output += "\n## Input Info :guitar:\n_Here's some pad and I/O information._\n"
        for issue, lines in pad_info.items():
            line_info = ", ".join(lines)  # Combine all line numbers
            output += f"{issue} (on {line_info})\n"

    ## Add computer info ##
    output += f"\n\n**Version:** {emulator_info['version']}\n**CPU:** {emulator_info['cpu']}\n**GPU:** {emulator_info['gpu']}\n{emulator_info['os']}"

    if language_message:
        output += f"\n\n{language_message}"

    return output, diagnostics_file