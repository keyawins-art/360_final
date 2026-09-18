import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    """Set background fill color for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    """Set padding/margins for a table cell in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    """Set subtle, professional borders on a table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="none"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def add_callout_box(doc, text_list, title="IMPORTANT NOTICE / KEY HIGHLIGHT", border_color="1E40AF", bg_color="F0F7FF"):
    """Adds a stylish callout box with a colored left accent border."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.8)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=180)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>'
        f'<w:top w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    run_title = p.add_run(f"📌 {title}")
    run_title.bold = True
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(11)
    run_title.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    
    for item in text_list:
        p_item = cell.add_paragraph()
        p_item.paragraph_format.space_before = Pt(2)
        p_item.paragraph_format.space_after = Pt(2)
        run_item = p_item.add_run(item)
        run_item.font.name = "Calibri"
        run_item.font.size = Pt(10)
        run_item.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def style_header_cell(cell, text, width=None):
    if width:
        cell.width = width
    set_cell_background(cell, "0F172A") # Dark Slate / Navy
    set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

def style_body_cell(cell, text, width=None, is_even=False, bold=False, color=None):
    if width:
        cell.width = width
    bg = "F8FAFC" if is_even else "FFFFFF"
    set_cell_background(cell, bg)
    set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Calibri"
    run.font.size = Pt(9.5)
    if color:
        run.font.color.rgb = color
    else:
        run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

def create_complete_english_word_document(output_path):
    doc = Document()
    
    # Page setup - Standard A4 / Letter with 0.75 inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
    
    # Palette definition
    NAVY = RGBColor(0x0F, 0x17, 0x2A)       # Slate 900
    BLUE = RGBColor(0x1E, 0x40, 0xAF)       # Blue 800
    TEAL = RGBColor(0x0F, 0x76, 0x6E)       # Teal 700
    DARK = RGBColor(0x33, 0x41, 0x55)       # Slate 700
    MUTED = RGBColor(0x64, 0x74, 0x8B)      # Slate 500
    
    # =========================================================================
    # DOCUMENT COVER / TITLE
    # =========================================================================
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(10)
    title_p.paragraph_format.space_after = Pt(2)
    run_title = title_p.add_run("360 INDUSTRIAL CASHEW SORTING & GRADING SYSTEM")
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(22)
    run_title.bold = True
    run_title.font.color.rgb = NAVY
    
    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_before = Pt(0)
    sub_p.paragraph_format.space_after = Pt(8)
    run_sub = sub_p.add_run("Complete Technical Architecture, File Directory Map, Frontend UI Capabilities & Operator Manual")
    run_sub.font.name = "Calibri"
    run_sub.font.size = Pt(13)
    run_sub.font.italic = True
    run_sub.font.color.rgb = BLUE
    
    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_before = Pt(0)
    meta_p.paragraph_format.space_after = Pt(14)
    run_meta = meta_p.add_run("Document Version: 2.1 | OS: Windows 10/11 x64 | Engine: PyTorch / ONNX Runtime CUDA (RTX 5050) | GUI: React 18 + FastAPI")
    run_meta.font.name = "Calibri"
    run_meta.font.size = Pt(9.5)
    run_meta.font.color.rgb = MUTED
    
    # Horizontal Divider Line
    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(14)
    r_div = div_p.add_run("―" * 65)
    r_div.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
    
    # =========================================================================
    # SECTION 1: EXECUTIVE SUMMARY
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("1. Executive Summary & System Overview")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        "The 360 Cashew Sorting and Grading System is an industrial-grade, multi-camera, high-speed computer vision automation platform. "
        "It is engineered to perform real-time optical inspection, sub-pixel size calculation (in millimeters), deep learning-based defect classification, "
        "and precise pneumatic air valve ejection across continuous industrial conveyor belts."
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    add_callout_box(
        doc,
        [
            "Dual-Camera Industrial Vision: Integrates two Hikvision GigE/USB3 cameras (Camera A for Belts 1-5; Camera B for Belts 6-10) processing up to 10 independent virtual zones simultaneously.",
            "GPU Accelerated AI Defect Detection: Powered by an optimized ONNX Runtime CUDA engine on NVIDIA GeForce RTX 5050, delivering ~9.9ms inference per object across 7 classes (Good, Bad, Blackdot, Brown, Multi, Oilly, Unpill).",
            "Sub-Millisecond Non-Blocking Ejection: Employs a dedicated multi-threaded Min-Heap priority queue (EjectionQueue) with hybrid sleep and spinlock timing to fire solenoids with zero camera frame lag.",
            "Rich Interactive Touch GUI: Developed in React 18 + Tailwind styling, hosted via FastAPI & PyWebview, featuring live real-time charts, telemetry, camera controls, zone calibration, time setting, and remote diagnostics.",
            "Standalone Desktop GUI & Zero Dependency Distribution: Built with FastAPI, PyWebview, and React Vite, completely bundled into an executable (.exe) requiring no external Python or Node.js runtime."
        ],
        title="CORE CAPABILITIES & SYSTEM SPECIFICATIONS"
    )
    
    # =========================================================================
    # SECTION 2: END-TO-END WORKING ARCHITECTURE (10 STAGES)
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("2. End-to-End Technical Working Pipeline (How the System Operates)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(
        "The entire processing workflow is divided into 10 synchronized stages designed for maximum throughput, precision, and reliability:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    stages = [
        ("Stage 1: High-Speed Continuous Frame Acquisition (Hikvision SDK)",
         "Hikvision industrial cameras run in dedicated background threads via the MvCameraControl SDK wrapper. Frames are acquired asynchronously in zero-copy memory buffers, preventing buffer overflow and eliminating video latency."),
        
        ("Stage 2: 10-Zone Independent Virtual Camera Cropping",
         "The full camera resolution is dynamically divided into 10 discrete inspection channels (Zones 1-5 mapped to Camera A, Zones 6-10 mapped to Camera B). Each zone has custom X, Y, Width, and Height coordinates stored in zones_config.json."),
        
        ("Stage 3: Advanced Pre-Processing & Optical Segmentation",
         "To handle uneven factory lighting, belt dust, and LED flicker, each zone frame undergoes Contrast Limited Adaptive Histogram Equalization (CLAHE). It is then thresholded using Adaptive Gaussian Thresholding and cleaned with morphological opening and closing filters to isolate cashew contours."),
        
        ("Stage 4: Sub-Pixel Rotation-Invariant Size Measurement (fitEllipse)",
         "Cashews naturally rotate on moving conveyors. Instead of simple bounding boxes, the vision pipeline fits an ellipse (cv2.fitEllipse) to extract major and minor axes. These dimensions are converted to exact millimeters using the calibrated ratio (PIXEL_TO_MM_RATIO = 0.111 mm/px)."),
        
        ("Stage 5: Constant-Velocity Kalman Filter Object Tracking",
         "Each object is assigned a persistent tracking ID. A C++ Kalman Filter (with a Python Kalman fallback) estimates position, instantaneous velocity, and acceleration. A trimmed median of the last 30 measurements is computed (Robust Size) to avoid size distortion when exiting the field of view."),
        
        ("Stage 6: Exit Line Crossing & Velocity Overshoot Compensation",
         "When a tracked cashew reaches 95% of the zone height (Trigger Line), the system records the exit timestamp. Any overshoot beyond the trigger line is dynamically compensated using the measured velocity (dt = dx / v) to guarantee exact millisecond precision."),
        
        ("Stage 7: GPU-Accelerated Defect Classification (CashewQualityFilter)",
         "High-resolution cashew crops are batched to the NVIDIA RTX 5050 ONNX Runtime CUDA Execution Provider. The neural network detects surface defects across 7 classes (Good, Bad, Blackdot, Brown, Multi, Oilly, Unpill) in less than 10 milliseconds."),
        
        ("Stage 8: Size Grade Mapping & Decision Matrix",
         "If the cashew is certified 'Good' by the AI filter, its robust millimeter size is matched against calibrated thresholds in wate/value.txt (grades: 400, 320, 240, 210, 180). Defective items are routed to defect/reject commands."),
        
        ("Stage 9: Non-Blocking Priority Ejection Queue (Min-Heap + Spinlock)",
         "The scheduled command is inserted into an EjectionQueue. The queue operates as a thread-safe Min-Heap with a hybrid wait mechanism: it sleeps during long delays and switches to a spinlock during the final 50ms before the target timestamp to fire solenoids with microsecond accuracy."),
        
        ("Stage 10: Serial Command Dispatch & Asynchronous Disk Logging",
         "The ejection command (e.g. '11|', '12|', '23|') is written over USB Serial at 115200 baud to the designated microcontroller (Controller A or Controller B). Concurrently, the AsyncImageSaver thread writes annotated cropped images to disk without stalling the real-time vision loop.")
    ]
    
    for title, desc in stages:
        p_s = doc.add_paragraph()
        p_s.paragraph_format.space_before = Pt(4)
        p_s.paragraph_format.space_after = Pt(4)
        r_num = p_s.add_run(f"✔ {title}\n")
        r_num.bold = True
        r_num.font.name = "Calibri"
        r_num.font.size = Pt(10.5)
        r_num.font.color.rgb = BLUE
        r_desc = p_s.add_run(desc)
        r_desc.font.name = "Calibri"
        r_desc.font.size = Pt(9.5)
        r_desc.font.color.rgb = DARK
        
    # =========================================================================
    # SECTION 3: FRONTEND USER INTERFACE CAPABILITIES & CONTROLS
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("3. Frontend UI Capabilities & Operator Control Center (What Can Be Done from Frontend)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(
        "The application provides a modern, touch-optimized graphical user interface built with React 18 and hosted via PyWebview. "
        "Operators and engineers can perform all machine controls, calibrations, hardware diagnostics, and remote maintenance directly from the UI:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    frontend_features = [
        ("1. Control Hub (Main Operator Dashboard)",
         "• Mode Execution Buttons: Start 'Grading Mode' (Dual-Camera live vision + AI defect detection + Kalman tracking), 'Default Mode' (Offline BMP folder batch processor), or 'Color Mode' (HSV color classification).\n"
         "• Emergency & Stop Control: 'Stop All' button immediately terminates all background processes, closes serial communication, and releases camera hardware gracefully.\n"
         "• Live Hardware Telemetry Bar: Real-time dynamic monitoring of CPU Load (%), GPU Utilization (%), GPU Temperature (°C), Total System Uptime (Hours/Minutes), and Live FPS counter.\n"
         "• Real-Time Grade Output Bar Chart: Interactive Recharts bar chart displaying live counts for each cashew grade (Grade 400, 320, 240, 210, 180) updated dynamically every 2 seconds.\n"
         "• Real-Time Status Ticker: Displays active process group count, current operational mode, and terminal feedback messages."),
        
        ("2. Camera Setting & Visual Zone Calibration Page",
         "• Multi-Camera Switching: Select between Camera 1 (Cam A), Camera 2 (Cam B), or Camera 3.\n"
         "• Live Video Streaming with Fullscreen Toggle: View real-time video feed (/api/video_feed) with overlay annotations and toggle fullscreen mode.\n"
         "• Live Hardware Parameter Sliders (Auto-Saving to camera_params.json):\n"
         "   - Exposure Time Slider: Adjust shutter speed (5,000 µs to 100,000 µs) in real-time to eliminate motion blur without restarting the app.\n"
         "   - Digital Gain Slider: Adjust sensor amplification (0.0 to 23.98 dB).\n"
         "   - Resolution & Offsets: Adjust Width, Height, OffsetX, and OffsetY with automatic buffer recalculation.\n"
         "• 10-Zone Geometry Calibration Tab: Configure X, Y, Width, and Height for all 10 inspection zones with live visual red bounding boxes and instant background synchronization.\n"
         "• Camera Hardware Discovery: 'Check Cameras' button queries the Hikvision MVS SDK, lists detected serial numbers, and allows 1-click camera serial assignment saved to wate/camera_ref.txt."),
        
        ("3. Customizations Page (Grade Size Calibration)",
         "• Millimeter Size Boundary Matrix: Configure precise Min and Max millimeter size cutoffs for all 5 commercial grades (400, 320, 240, 210, 180).\n"
         "• Touchscreen Numeric Keypad: Integrated on-screen numpad for seamless touch-screen operation on factory panel PCs.\n"
         "• Persistent Configuration: Changes are written directly to wate/value.txt and immediately loaded by vision workers."),
        
        ("4. Time Setting Page (Pneumatic Pulse Duration Management)",
         "• Belt Channel Selector: Select from Belt 1 to Belt 15.\n"
         "• 7 Solenoid Timing Pulse Boxes: Configure 4-digit pulse durations (0000 to 9999 ms) for all 7 ejection ports per belt.\n"
         "• 'Apply to All Belts' Global Sync: Copy Belt 1 configuration to Belts 2 through 15 in a single click.\n"
         "• Bulk File Serialization: Saves timing strings to wate/1(A)-time.txt through wate/15(A)-time.txt."),
        
        ("5. Air Valve Testing & Pneumatic Diagnostics Page",
         "• 15-Belt Multi-Controller Testing Grid: Dedicated testing buttons for all 15 belts across 3 paginated controller panels:\n"
         "   - Page 1: Belts 1 to 5 (Routed to Controller A / com_port(a).txt)\n"
         "   - Page 2: Belts 6 to 10 (Routed to Controller B / com_port(b).txt)\n"
         "   - Page 3: Belts 11 to 15 (Routed to Controller C / com_port(c).txt)\n"
         "• Independent Solenoid Firing: Click any of the 7 ports on any belt to trigger an immediate air pulse for checking nozzle blockage or air pressure alignment.\n"
         "• Non-Resetting Serial Connection: Persistent serial caching prevents microcontroller bootloader reset during rapid test firing."),
        
        ("6. Settings & Serial COM Port Management Page",
         "• Automated COM Port Scanner: Scans Windows serial subsystem (/api/comport-check) and populates active COM ports (e.g. COM3, COM4, COM5).\n"
         "• Controller COM Assignment: Easily bind Controller A, Controller B, and Controller C to detected COM ports with auto-synchronization to wate/comport_ref.txt and legacy paths.\n"
         "• Main Settings Belt Value Dispatch: Send custom strings directly to specific belt modules."),
        
        ("7. Remote Support, System Actions & Security",
         "• Remote TeamViewer Launch: Launches TeamViewer in the background via /api/open-teamviewer for remote developer maintenance.\n"
         "• Native Wi-Fi Setup: Triggers the native Windows Wi-Fi network panel directly from the UI (/api/open-wifi).\n"
         "• On-Screen Virtual Keyboard: Launches the Windows OSK (osk.exe) for full typing capability on touchscreen displays.\n"
         "• Protected Settings Access (PIN/Password Modal): Secures sensitive pages (Camera Settings, Customizations, Settings) with an authentication dialog to prevent accidental changes by factory operators.\n"
         "• Device Shutdown & Restart: Safe system power management dialogs with confirmation modals to prevent file corruption.")
    ]
    
    for title, desc in frontend_features:
        p_f = doc.add_paragraph()
        p_f.paragraph_format.space_before = Pt(6)
        p_f.paragraph_format.space_after = Pt(4)
        r_ft = p_f.add_run(f"🖥️ {title}\n")
        r_ft.bold = True
        r_ft.font.name = "Calibri"
        r_ft.font.size = Pt(11)
        r_ft.font.color.rgb = BLUE
        r_fd = p_f.add_run(desc)
        r_fd.font.name = "Calibri"
        r_fd.font.size = Pt(9.5)
        r_fd.font.color.rgb = DARK
        
    # Frontend Pages Summary Table
    p_tbl_intro = doc.add_paragraph()
    p_tbl_intro.paragraph_format.space_before = Pt(8)
    p_tbl_intro.paragraph_format.space_after = Pt(4)
    r_ti = p_tbl_intro.add_run("Quick Reference: Frontend Navigation Pages & Control Summary")
    r_ti.bold = True
    r_ti.font.name = "Calibri"
    r_ti.font.size = Pt(10.5)
    r_ti.font.color.rgb = NAVY
    
    ui_table_data = [
        ("Page / Action Name", "Navigation Type", "Key Functions & Operator Controls"),
        ("Control Hub", "Main Dashboard", "Run Grading, Run Default, Run Color, Stop All, Telemetry (CPU/GPU/FPS), Real-Time Grade Chart."),
        ("Camera Setting", "Configuration (Protected)", "Live Video Feed (Fullscreen), Exposure & Gain Sliders, 10-Zone Coordinates, Camera Auto-Check."),
        ("Customizations", "Configuration (Protected)", "Millimeter Size Thresholds for Grades (400, 320, 240, 210, 180), Touch Numeric Keypad, Save value.txt."),
        ("Time Setting", "Pneumatic Timing", "15 Belts × 7 Pulse Timing Boxes, Touch Number Pad, 'Apply to All Belts' Global Copy, Save *.txt."),
        ("Air Valve", "Hardware Test", "15 Belts × 7 Solenoid Trigger Buttons, Paginated Controllers (Pages 1-3 for Controllers A, B, C)."),
        ("Settings", "Configuration (Protected)", "Scan Windows COM Ports, Assign Controller A/B/C Serial Ports, Custom Belt Parameter Dispatch."),
        ("Team Viewer", "Remote Support", "Starts background TeamViewer remote desktop service for engineering diagnostics."),
        ("Wi-Fi Connect", "Network Utility", "Opens Windows native Wi-Fi connection manager directly from GUI."),
        ("Virtual Keyboard", "Accessibility Action", "Launches Windows On-Screen Keyboard (osk.exe) for touchscreen typing."),
        ("Shutdown / Restart", "System Action", "Initiates clean Windows OS shutdown or reboot with confirmation safety dialogs.")
    ]
    
    tbl_ui = doc.add_table(rows=len(ui_table_data), cols=3)
    tbl_ui.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_ui.autofit = False
    set_table_borders(tbl_ui)
    
    col_w_ui = [Inches(1.8), Inches(1.8), Inches(3.2)]
    for row_idx, row in enumerate(ui_table_data):
        is_header = (row_idx == 0)
        is_even = (row_idx % 2 == 0)
        for col_idx, text in enumerate(row):
            cell = tbl_ui.cell(row_idx, col_idx)
            if is_header:
                style_header_cell(cell, text, col_w_ui[col_idx])
            else:
                style_body_cell(cell, text, col_w_ui[col_idx], is_even, bold=(col_idx == 0))
                
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # =========================================================================
    # SECTION 4: COMPREHENSIVE FILE & DIRECTORY DIRECTORY MAP
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("4. Complete File & Directory Map (Repository Structure & Component Roles)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(
        "Below is the complete architectural layout of every file and folder in the project, detailing its location and precise technical responsibility:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    file_map_data = [
        ("File / Folder Path", "Component Layer", "Detailed Technical Function & Purpose"),
        ("START_360_APP.bat", "Root Launcher", "Convenience batch script to launch the standalone compiled executable in dist/360_App/."),
        ("RUN_BUILD_EXE.bat", "Build Automation", "Executes full production build: compiles Vite React frontend and bundles PyInstaller .exe."),
        ("build_full_project.py", "Build Automation", "Master Python build automation script orchestrating PyInstaller, frontend dist packaging, and ZIP creation."),
        ("zones_config.json", "Runtime Config", "JSON schema defining the 10 inspection zones (X, Y, Width, Height) for Cameras A & B."),
        ("camera_params.json", "Hardware Config", "Camera hardware registers: manual exposure time, digital gain, frame width, height, and offsets."),
        ("best.onnx / best.pt", "Deep Learning Model", "Trained YOLO defect detection neural network weights (ONNX format optimized for RTX CUDA)."),
        ("camera_log.txt", "Diagnostics Log", "Real-time diagnostic log file recording camera connection events, frame rates, and errors."),
        ("grading/initial.py", "Core Vision Engine", "Primary dual-camera vision pipeline, 10-zone segmentation, Kalman tracking, and AI grading."),
        ("grading/tracker_adapter.py", "Tracking Bridge", "Python C-extension wrapper interfacing with the high-speed C++ Kalman Filter."),
        ("grading/fallback_tracker.py", "Tracking Fallback", "Pure Python constant-velocity Kalman Filter tracker used when C++ binary is absent."),
        ("grading/ejection_queue.py", "Pneumatic Timing", "Thread-safe Min-Heap priority queue executing high-precision non-blocking serial ejection commands."),
        ("backend/server.py", "FastAPI & Webview", "High-performance API server managing system telemetry, hardware routing, and native PyWebview window."),
        ("frontend/src/App.jsx", "React GUI", "Main touch-screen user interface: dashboard telemetry, live charts, calibration tools, and valve tests."),
        ("frontend/src/App.css", "UI Styling", "Modern dark-themed glassmorphic styling, responsive layout grids, and interactive animations."),
        ("wate/value.txt", "Calibration Config", "Millimeter boundary ranges mapping cashew dimensions to industry grades (400, 320, 240, 210, 180)."),
        ("wate/camera_ref.txt", "Hardware Config", "Hardware serial numbers for Camera A and Camera B (Hikvision GigE/USB3 identifiers)."),
        ("wate/comport_ref.txt", "Hardware Config", "Active COM port assignments for microcontroller serial connections (COM1, COM2, etc.)."),
        ("wate/com_port(a/b/c).txt", "Hardware Config", "Serial port configuration files read by Controller A, Controller B, and Controller C."),
        ("wate/1(A)-time.txt..15(A)", "Timing Parameters", "Pneumatic box pulse time configuration files for Belts 1 through 15."),
        ("defoult/defoult_with_time(A).py", "Batch Processor", "Offline folder watcher mode processing pre-captured BMP images from disk."),
        ("grading_color/grading,color..py", "Color Engine", "Color classification engine utilizing HSV color space segmentation."),
        ("dist/360_App/360_App.exe", "Release Binary", "Self-contained standalone Windows executable ready for deployment on factory PCs."),
        ("Python/MvImport/", "SDK Wrapper", "Official Hikvision MVS Industrial Camera SDK Python CTypes wrapper bindings.")
    ]
    
    tbl = doc.add_table(rows=len(file_map_data), cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    set_table_borders(tbl)
    
    col_widths = [Inches(2.2), Inches(1.4), Inches(3.2)]
    for row_idx, row in enumerate(file_map_data):
        is_header = (row_idx == 0)
        is_even = (row_idx % 2 == 0)
        for col_idx, text in enumerate(row):
            cell = tbl.cell(row_idx, col_idx)
            if is_header:
                style_header_cell(cell, text, col_widths[col_idx])
            else:
                style_body_cell(cell, text, col_widths[col_idx], is_even, bold=(col_idx == 0))
                
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # =========================================================================
    # SECTION 5: HARDWARE, CONTROLLERS & VALVE COMMAND PROTOCOL
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("5. Hardware & Valve Command Protocol (Ejection Matrix)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        "The system routes specific ASCII commands over serial communication (115200 Baud, 8-N-1) based on the evaluated grade and zone. "
        "Camera A controls Belts 1-5 via Controller A, while Camera B controls Belts 6-10 via Controller B:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    port_mapping_data = [
        ("Zone / Belt", "Camera & Controller", "Grade 400", "Grade 320", "Grade 240", "Grade 210", "Grade 180", "Defect / Reject"),
        ("Zone-1 (Belt 1)", "Cam A / Controller A", "11|", "12|", "13|", "14|", "15|", "16|"),
        ("Zone-2 (Belt 2)", "Cam A / Controller A", "22|", "23|", "24|", "25|", "26|", "21| / 22|"),
        ("Zone-3 (Belt 3)", "Cam A / Controller A", "33|", "34|", "35|", "36|", "41|", "33|"),
        ("Zone-4 (Belt 4)", "Cam A / Controller A", "44|", "45|", "46|", "51|", "52|", "44|"),
        ("Zone-5 (Belt 5)", "Cam A / Controller A", "55|", "56|", "61|", "62|", "63|", "55|"),
        ("Zone-6 (Belt 6)", "Cam B / Controller B", "11|", "12|", "13|", "14|", "15|", "16|"),
        ("Zone-7 (Belt 7)", "Cam B / Controller B", "22|", "23|", "24|", "25|", "26|", "22|"),
        ("Zone-8 (Belt 8)", "Cam B / Controller B", "33|", "34|", "35|", "36|", "41|", "33|"),
        ("Zone-9 (Belt 9)", "Cam B / Controller B", "44|", "45|", "46|", "51|", "52|", "44|"),
        ("Zone-10 (Belt 10)", "Cam B / Controller B", "55|", "56|", "61|", "62|", "63|", "55|")
    ]
    
    tbl_p = doc.add_table(rows=len(port_mapping_data), cols=8)
    tbl_p.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_p.autofit = False
    set_table_borders(tbl_p)
    
    pw = [Inches(1.3), Inches(1.5), Inches(0.6), Inches(0.6), Inches(0.6), Inches(0.6), Inches(0.6), Inches(0.7)]
    for row_idx, row in enumerate(port_mapping_data):
        is_header = (row_idx == 0)
        is_even = (row_idx % 2 == 0)
        for col_idx, text in enumerate(row):
            cell = tbl_p.cell(row_idx, col_idx)
            if is_header:
                style_header_cell(cell, text, pw[col_idx])
            else:
                style_body_cell(cell, text, pw[col_idx], is_even, bold=(col_idx == 0))
                
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # =========================================================
    # SECTION 6: STEP-BY-STEP OPERATOR GUIDE (HOW TO USE)
    # =========================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("6. Step-by-Step Operator Manual (Daily Operations Workflow)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        "Follow this standard operating procedure (SOP) to start, configure, run, and maintain the grading system:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    user_steps = [
        ("Step 1: Launching the Application",
         "Double-click 'START_360_APP.bat' on the Desktop or run 'dist/360_App/360_App.exe'.\n"
         "• The FastAPI backend initializes on localhost port 8000.\n"
         "• The dedicated desktop touchscreen application opens automatically displaying system health, CPU/GPU telemetry, and mode selectors."),
        
        ("Step 2: Verifying Hardware Connections (Cameras & COM Ports)",
         "Navigate to the 'Camera Settings' or 'Comport Settings' page in the UI:\n"
         "• Click 'Check Cameras': The system queries the MVS SDK and lists detected camera serial numbers. Assign Camera 1 and Camera 2 to their respective positions and save.\n"
         "• Click 'Check COM Ports': The system scans Windows serial ports (e.g., COM3, COM4). Assign Controller A (Belts 1-5) and Controller B (Belts 6-10) and save."),
        
        ("Step 3: Setting Calibration & Grade Size Thresholds",
         "Navigate to the 'Customizations' tab to define millimeter size cutoffs for each grade level:\n"
         "• Grade 400: e.g., Min 16.30 mm, Max 29.00 mm\n"
         "• Grade 320: e.g., Min 18.00 mm, Max 30.50 mm\n"
         "• Grades 240, 210, 180: Set exact boundaries per batch specification. Values are saved directly to wate/value.txt."),
        
        ("Step 4: Aligning Camera & Zone Calibration",
         "Navigate to the 'Zones Configuration' tab:\n"
         "• Click 'Start Preview' to inspect the live video feed.\n"
         "• Adjust exposure time (recommended 5,000 - 8,000 microseconds) and gain using the sliders to eliminate motion blur.\n"
         "• Verify that the 10 colored zone boundary boxes strictly overlap the belt channels without clipping conveyor edges."),
        
        ("Step 5: Starting Live Real-Time Grading",
         "From the main 'Control Hub' dashboard, press 'Run Grading':\n"
         "• The split dual-camera window appears (Left: Camera A / Zones 1-5; Right: Camera B / Zones 6-10).\n"
         "• Real-time overlays display bounding contours, tracked IDs, size in mm, and defect classifications.\n"
         "• High-speed pneumatic air valves trigger automatically based on the configured delay times."),
        
        ("Step 6: Testing Pneumatic Air Valves Manually",
         "Navigate to the 'Air Valve' tab to verify pneumatic pressure and nozzle alignment:\n"
         "• Paginated controls support all 15 belts (Page 1: Belts 1-5, Page 2: Belts 6-10, Page 3: Belts 11-15).\n"
         "• Click any valve port button (Ports 1 to 7) to trigger an immediate air pulse and confirm solenoid responsiveness."),
        
        ("Step 7: Halting Operations and Safe Shutdown",
         "To stop grading, click 'Stop All' on the dashboard.\n"
         "• All active background processes, camera acquisition loops, and serial connections are cleanly terminated.\n"
         "• To shut down or reboot the factory machine, use the 'Shutdown' or 'Restart' action buttons in the application header.")
    ]
    
    for title, desc in user_steps:
        p_s = doc.add_paragraph()
        p_s.paragraph_format.space_before = Pt(6)
        p_s.paragraph_format.space_after = Pt(4)
        r_t = p_s.add_run(f"👉 {title}\n")
        r_t.bold = True
        r_t.font.name = "Calibri"
        r_t.font.size = Pt(10.5)
        r_t.font.color.rgb = NAVY
        r_d = p_s.add_run(desc)
        r_d.font.name = "Calibri"
        r_d.font.size = Pt(9.5)
        r_d.font.color.rgb = DARK
        
    # =========================================================================
    # SECTION 7: KEYBOARD SHORTCUTS IN LIVE GRADING
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("7. Live Camera Keyboard Shortcuts & Hotkeys")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        "When the live OpenCV 'Full Camera' window is focused during grading, operators can adjust zone positions and controls using keyboard hotkeys:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    hotkeys_data = [
        ("Key / Button", "Assigned Function", "Operational Behavior & Effect"),
        ("1 to 5", "Select Zone 1 to Zone 5", "Selects Camera A inspection zones for immediate geometry adjustments."),
        ("6 to 9, 0", "Select Zone 6 to Zone 10", "Selects Camera B inspection zones (Key '0' corresponds to Zone 10)."),
        ("TAB or 'N'", "Cycle Selection", "Sequentially selects the next active zone in ascending order."),
        ("Arrow Keys / W-A-S-D", "Translate Zone Box", "Shifts the selected zone boundary Up, Down, Left, or Right by 10 pixels."),
        ("+ / - (or K / H)", "Adjust Width", "Increases or decreases the width of the selected zone box."),
        ("[ / ] (or U / J)", "Adjust Height", "Decreases or increases the height of the selected zone box."),
        ("'C' Key", "Save Zone Layout", "Persists current coordinates of all 10 zones directly to zones_config.json."),
        ("'Q' Key", "Toggle Display", "Hides the heavy OpenCV window to save GPU rendering while background grading continues."),
        ("ESC Key", "Stop & Terminate", "Gracefully closes camera streams, releases serial ports, and shuts down the vision loop.")
    ]
    
    tbl_k = doc.add_table(rows=len(hotkeys_data), cols=3)
    tbl_k.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_k.autofit = False
    set_table_borders(tbl_k)
    
    kw = [Inches(1.8), Inches(2.0), Inches(3.0)]
    for row_idx, row in enumerate(hotkeys_data):
        is_header = (row_idx == 0)
        is_even = (row_idx % 2 == 0)
        for col_idx, text in enumerate(row):
            cell = tbl_k.cell(row_idx, col_idx)
            if is_header:
                style_header_cell(cell, text, kw[col_idx])
            else:
                style_body_cell(cell, text, kw[col_idx], is_even, bold=(col_idx == 0))
                
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # =========================================================================
    # SECTION 8: BUILD AUTOMATION & EXE DISTRIBUTION
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("8. Build Automation, Packaging & Deployment (.EXE Distribution)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        "The project includes an end-to-end build pipeline allowing developers to package updates into a standalone portable ZIP:"
    )
    r.font.name = "Calibri"
    r.font.size = Pt(10.5)
    r.font.color.rgb = DARK
    
    add_callout_box(
        doc,
        [
            "One-Click Build Command: Run 'RUN_BUILD_EXE.bat' or execute 'python build_full_project.py' in the terminal.",
            "Step 1 (Frontend): Vite compiles the React single-page application into optimized static assets in frontend/dist/.",
            "Step 2 (PyInstaller Packaging): Bundles FastAPI, Uvicorn, OpenCV, ONNX Runtime, PyWebview, and SDK bindings into dist/360_App/.",
            "Step 3 (Asset Aggregation): Automatically synchronizes zones_config.json, camera_params.json, best.onnx, and configuration directories into the bundle.",
            "Step 4 (Portable ZIP Creation): Generates dist/360_App_Portable.zip. This archive can be extracted on any standard 64-bit Windows PC and run immediately via START_APP.bat without installing Python, Node.js, or external drivers."
        ],
        title="STANDALONE DISTRIBUTION ARCHITECTURE"
    )
    
    # =========================================================================
    # SECTION 9: TROUBLESHOOTING & MAINTENANCE
    # =========================================================================
    h1 = doc.add_heading(level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)
    r = h1.add_run("9. Diagnostic & Troubleshooting Guide (Common Issues & Solutions)")
    r.font.name = "Calibri"
    r.font.size = Pt(15)
    r.bold = True
    r.font.color.rgb = NAVY
    
    troubleshoot_data = [
        ("Diagnostic Symptom", "Probable Root Cause", "Actionable Engineering Remedy"),
        ("Camera Not Found / 'EnumDevices Failed'", "Physical connection error, network IP mismatch, or missing MVS driver.", "1. Verify USB3 / GigE cable connection.\n2. Open Hikvision MVS Studio to verify camera detection and IP subnet.\n3. Use 'Check Cameras' in settings to refresh serial ID."),
        ("Serial Access Denied / 'Could Not Open Port'", "COM port is locked by another instance or external serial monitor.", "1. Ensure Arduino IDE Serial Monitor is closed.\n2. Click 'Stop All' on the dashboard to kill zombie worker processes.\n3. Verify COM port index in Windows Device Manager."),
        ("Ejection Timing Error / Air Fires Late", "Conveyor belt velocity does not match the configured queue delay.", "1. Adjust DELAY_SECONDS or ZONE_DELAY_MAP in initial.py.\n2. For faster belt speeds, reduce delay (e.g., from 5.50s to 5.20s)."),
        ("False Detections / Roller Noise Captured", "Zone boundary is positioned over mechanical rollers.", "1. Use arrow keys to translate the zone box within the active belt area.\n2. MIN_CASHEW_AREA (3500) and MAX_CASHEW_MM (33.0) filters automatically reject large rollers."),
        ("Motion Blur / Smudged Cashew Contours", "Camera exposure time is too long relative to belt speed.", "1. Reduce exposure time in camera_params.json (set between 4,000 and 8,000 µs).\n2. Increase external industrial LED illumination on the inspection zone."),
        ("GPU ONNX CUDA Provider Fallback", "NVIDIA CUDA runtime or GPU driver incompatibility.", "1. The engine automatically falls back to CPUExecutionProvider with zero downtime.\n2. To re-enable RTX 5050 GPU acceleration, ensure the latest NVIDIA display drivers are installed.")
    ]
    
    tbl_t = doc.add_table(rows=len(troubleshoot_data), cols=3)
    tbl_t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_t.autofit = False
    set_table_borders(tbl_t)
    
    tw = [Inches(1.8), Inches(1.8), Inches(3.2)]
    for row_idx, row in enumerate(troubleshoot_data):
        is_header = (row_idx == 0)
        is_even = (row_idx % 2 == 0)
        for col_idx, text in enumerate(row):
            cell = tbl_t.cell(row_idx, col_idx)
            if is_header:
                style_header_cell(cell, text, tw[col_idx])
            else:
                style_body_cell(cell, text, tw[col_idx], is_even, bold=(col_idx == 0))
                
    doc.add_paragraph().paragraph_format.space_after = Pt(14)
    
    # Document Footer / Summary Note
    end_p = doc.add_paragraph()
    end_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_end = end_p.add_run("― End of 360 Cashew Sorting & Grading System Complete Technical Manual ―")
    r_end.font.name = "Calibri"
    r_end.font.size = Pt(9.5)
    r_end.font.italic = True
    r_end.font.color.rgb = MUTED
    
    doc.save(output_path)
    print(f"[SUCCESS] Complete English Word document with Frontend UI guide successfully saved at: {output_path}")

if __name__ == "__main__":
    out_file = os.path.join(r"c:\Users\i7\Desktop\360", "360_Project_Complete_Guide.docx")
    create_complete_english_word_document(out_file)
