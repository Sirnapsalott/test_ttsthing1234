import streamlit as st
import os
import sys
import PyPDF2
import numpy as np
import soundfile as sf
import customtkinter as ctk
from tkinter import messagebox, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
from kokoro import KPipeline
import threading
import platform
import subprocess

# Global settings
charlimit = 4095
voice = "af_heart"  # Change as needed
speed = 1
pdf_file_path = ""

def toggle_ui_state(enabled=True):
    """Enable or disable UI elements during processing."""
    state = 'normal' if enabled else 'disabled'
    # File selection controls
    browse_pdf_button.configure(state=state)
    use_clipboard_button.configure(state=state)
    pdf_file_label.configure(state=state)
    # Output directory controls
    output_dir_entry.configure(state=state)
    browse_output_button.configure(state=state)
    # Start button
    start_button.configure(state=state)
    # Drag and drop area
    if enabled:
        drop_frame.pack(expand=True, fill="both", padx=20, pady=(10, 20))
    else:
        drop_frame.pack_forget()

def open_directory(path):
    """Open the directory in the system's file explorer."""
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])

def process_text(full_text, base_name):
    """Process text and convert to speech."""
    try:
        # Split the text into smaller chunks if needed
        clauses = full_text.split('.')
        for i, clause in enumerate(clauses):
            if len(clause) > charlimit:
                clauses[i] = clause[:charlimit]
                clauses.insert(i + 1, clause[charlimit:])

        chunks = []
        current_chunk = ""
        for clause in clauses:
            clause = clause.strip()
            if clause:
                potential_chunk = (current_chunk + clause + '.').strip()
                if len(potential_chunk) <= charlimit:
                    current_chunk = potential_chunk + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = clause + "."
        if current_chunk:
            chunks.append(current_chunk.strip())

        print(f"Processed {len(full_text)} characters split into {len(chunks)} chunk(s).")

        output_dir = output_dir_entry.get() or "/Users/bryan/Downloads"
        os.makedirs(output_dir, exist_ok=True)

        pipeline = KPipeline(lang_code="a")
        all_audio_segments = []
        total_chunks = len(chunks)

        for chunk_idx, chunk in enumerate(chunks):
            print(f"Processing chunk {chunk_idx + 1} ({len(chunk)} chars)...")
            generator_list = list(pipeline(chunk, voice=voice, speed=speed, split_pattern=r"(?<=[.?!])\s+"))
            audio_list = []
            num_segments = len(generator_list) or 1

            for seg_idx, (gs, ps, audio) in enumerate(generator_list):
                audio_list.append(audio)
                overall_progress = ((chunk_idx + (seg_idx + 1) / num_segments) / total_chunks) * 100
                progress_bar.set(overall_progress / 100)
                progress_label.configure(text=f"Progress: {overall_progress:.1f}%")
                root.update_idletasks()

            if audio_list:
                combined_audio = np.concatenate(audio_list)
                chunk_out_file = os.path.join(output_dir, f"{base_name}_chunk{chunk_idx + 1}.wav")
                sf.write(chunk_out_file, combined_audio, 24000)
                all_audio_segments.append(combined_audio)

        # Combine temporary chunks into one final file
        if all_audio_segments:
            final_audio = np.concatenate(all_audio_segments)
            final_output_file = os.path.join(output_dir, f"{base_name}_complete.wav")
            sf.write(final_output_file, final_audio, 24000)

            # Clean up chunk files
            for idx in range(len(chunks)):
                chunk_file = os.path.join(output_dir, f"{base_name}_chunk{idx + 1}.wav")
                try:
                    os.remove(chunk_file)
                except Exception as e:
                    print(f"Could not delete {chunk_file}: {e}")

            root.after(0, lambda: messagebox.showinfo("Success", f"Audio saved to:\n{final_output_file}"))
            open_directory(output_dir)
        else:
            root.after(0, lambda: messagebox.showerror("Error", "No audio segments generated"))
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Error", str(e)))
    finally:
        root.after(0, lambda: toggle_ui_state(True))

def process_pdf(pdf_path):
    """Extract text from PDF and process it."""
    try:
        pdf_path = pdf_path.strip('{}')
        if not pdf_path.lower().endswith(".pdf"):
            raise ValueError("The selected file is not a PDF!")

        base = os.path.basename(pdf_path).split(".")[0]
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            full_text = " ".join(
                page.extract_text().replace("\n", " ") 
                for page in reader.pages if page.extract_text()
            )

        process_text(full_text, base)
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Error", str(e)))
        root.after(0, lambda: toggle_ui_state(True))

def start_processing():
    global pdf_file_path
    if not pdf_file_path:
        messagebox.showerror("Error", "Please select a PDF file first.")
        return
    toggle_ui_state(False)
    progress_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 20))
    progress_bar.set(0)
    progress_label.configure(text="Progress: 0%")
    threading.Thread(target=process_pdf, args=(pdf_file_path,), daemon=True).start()

def browse_pdf_file():
    global pdf_file_path
    file_path = filedialog.askopenfilename(title="Select PDF", filetypes=[("PDF Files", "*.pdf")])
    if file_path:
        pdf_file_path = file_path
        pdf_file_label.configure(text=f"Selected PDF: {os.path.basename(file_path)}")

def use_clipboard():
    """Use clipboard content as text source."""
    try:
        clipboard_text = root.clipboard_get().strip()
        if not clipboard_text:
            raise ValueError("Clipboard is empty!")
        toggle_ui_state(False)
        progress_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 20))
        progress_bar.set(0)
        progress_label.configure(text="Progress: 0%")
        threading.Thread(target=process_text, args=(clipboard_text, "clipboard"), daemon=True).start()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def drop(event):
    global pdf_file_path
    pdf_file_path = event.data.split()[0].strip('{}')
    pdf_file_label.configure(text=f"Selected PDF: {os.path.basename(pdf_file_path)}")

# ------------------- GUI Setup ------------------- #
ctk.set_appearance_mode("Dark")            # "System", "Dark", or "Light"
ctk.set_default_color_theme("blue")        # Built-in themes: "blue", "green", "dark-blue"

root = TkinterDnD.Tk()
root.title("PDF to Speech")
root.geometry("600x500")

# ---------- Output Directory Frame ---------- #
output_dir_frame = ctk.CTkFrame(root)
output_dir_frame.pack(side="top", fill="x", padx=20, pady=(20, 10))

output_dir_label = ctk.CTkLabel(output_dir_frame, text="Output Directory:")
output_dir_label.pack(side="left", padx=(0, 10))

output_dir_entry = ctk.CTkEntry(output_dir_frame, width=300)
output_dir_entry.pack(side="left")
output_dir_entry.insert(0, "/Users/bryan/Downloads")

browse_output_button = ctk.CTkButton(
    output_dir_frame,
    text="Browse",
    command=lambda: [
        output_dir_entry.delete(0, ctk.END),
        output_dir_entry.insert(0, filedialog.askdirectory())
    ]
)
browse_output_button.pack(side="left", padx=10)

# ---------- File Selection Frame ---------- #
file_frame = ctk.CTkFrame(root)
file_frame.pack(side="top", fill="x", padx=20, pady=10)

browse_pdf_button = ctk.CTkButton(file_frame, text="Browse PDF", command=browse_pdf_file)
browse_pdf_button.pack(side="left", padx=(0, 10))

use_clipboard_button = ctk.CTkButton(file_frame, text="Use Clipboard", command=use_clipboard)
use_clipboard_button.pack(side="left", padx=(0, 10))

pdf_file_label = ctk.CTkLabel(file_frame, text="No PDF selected", text_color="cyan")
pdf_file_label.pack(side="left")

# ---------- Start Button ---------- #
start_button = ctk.CTkButton(
    root, 
    text="Start Processing", 
    font=("Arial", 14, "bold"), 
    command=start_processing
)
start_button.pack(pady=(5, 10))

# ---------- Progress Frame ---------- #
progress_frame = ctk.CTkFrame(root)
progress_bar = ctk.CTkProgressBar(progress_frame, width=400)
progress_bar.set(0)
progress_bar.pack(side="left", padx=(10, 5), pady=10)

progress_label = ctk.CTkLabel(progress_frame, text="Progress: 0%")
progress_label.pack(side="left", padx=5)

# ---------- Drag and Drop Frame ---------- #
drop_frame = ctk.CTkFrame(root, fg_color="transparent", border_width=2, corner_radius=10)
drop_frame.pack(expand=True, fill="both", padx=20, pady=(10, 20))

drop_label = ctk.CTkLabel(
    drop_frame,
    text="Drag and drop a PDF file here",
    font=("Arial", 16, "bold"),
    text_color="silver"
)
drop_label.pack(expand=True, fill="both")
drop_label.drop_target_register(DND_FILES)
drop_label.dnd_bind("<<Drop>>", drop)

root.mainloop()
