import os
import glob

base_dir = r"d:\Keya Work\360"
wate_dir = os.path.join(base_dir, "wate")
os.makedirs(wate_dir, exist_ok=True)

files_to_create = {
    "value.txt": "100",
    "4(A)-time.txt": "10|20|30",
    "4(B)-time.txt": "10|20|30",
    "4(C)-time.txt": "10|20|30",
    "4(D)-time.txt": "10|20|30",
    "com_port(a).txt": "COM1",
    "com_port(b).txt": "COM2",
    "com_port(c).txt": "COM3",
    "com_port(d).txt": "COM4",
}

for fname, content in files_to_create.items():
    with open(os.path.join(wate_dir, fname), "w") as f:
        f.write(content)

for i in range(1, 5):
    os.makedirs(os.path.join(wate_dir, f"Con_{i}_Images"), exist_ok=True)

folders_to_process = ["defoult", "grading", "grading_color"]

for folder in folders_to_process:
    folder_path = os.path.join(base_dir, folder)
    if not os.path.exists(folder_path): continue
    
    for py_file in glob.glob(os.path.join(folder_path, "*.py")):
        with open(py_file, "r") as f:
            content = f.read()
            
        new_content = content.replace(r"D:\4_belt_main\4_belt\range\value.txt", r"D:\Keya Work\360\wate\value.txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\time\4(A)-time.txt", r"D:\Keya Work\360\wate\4(A)-time.txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\time\4(B)-time.txt", r"D:\Keya Work\360\wate\4(B)-time.txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\time\4(C)-time.txt", r"D:\Keya Work\360\wate\4(C)-time.txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\time\4(D)-time.txt", r"D:\Keya Work\360\wate\4(D)-time.txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\Test_checkup\com_port(a).txt", r"D:\Keya Work\360\wate\com_port(a).txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\Test_checkup\com_port(b).txt", r"D:\Keya Work\360\wate\com_port(b).txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\Test_checkup\com_port(c).txt", r"D:\Keya Work\360\wate\com_port(c).txt")
        new_content = new_content.replace(r"D:\4_belt_main\4_belt\Test_checkup\com_port(d).txt", r"D:\Keya Work\360\wate\com_port(d).txt")
        new_content = new_content.replace(r"D:\Kesyu_250524_4_Belts\Images\Con_1_Images", r"D:\Keya Work\360\wate\Con_1_Images")
        new_content = new_content.replace(r"D:\Kesyu_250524_4_Belts\Images\Con_2_Images", r"D:\Keya Work\360\wate\Con_2_Images")
        new_content = new_content.replace(r"D:\Kesyu_250524_4_Belts\Images\Con_3_Images", r"D:\Keya Work\360\wate\Con_3_Images")
        new_content = new_content.replace(r"D:\Kesyu_250524_4_Belts\Images\Con_4_Images", r"D:\Keya Work\360\wate\Con_4_Images")

        if content != new_content:
            with open(py_file, "w") as f:
                f.write(new_content)
            print(f"Updated paths in {py_file}")

print("All done!")
