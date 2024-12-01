import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import pysubs2
import threading
import torch
import transformers
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from accelerate import init_empty_weights, infer_auto_device_map, load_checkpoint_and_dispatch
import re
from pymkv import MKVFile
import os
import subprocess


anime_variable = ""

def extract_mkv_sub(mkv_file, file_output, track_id):
    # Extract the selected track from an MKV file using mkvextract

    try:
        # Set the path for the output file
        sub_name = os.path.join(file_output, f"sub_{track_id}.ass")  # Creates a .ass file for the output

        # Command to extract the subtitle track
        command_extract = [
            "mkvextract",
            "tracks",
            mkv_file,
            f"{track_id}:{sub_name}"
        ]

        # Execute the extraction command
        result = subprocess.run(command_extract, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check the command's return status
        if result.returncode != 0:
            raise Exception(f"Error executing mkvextract: {result.stderr}")

        print(f"Subtitle successfully extracted: {sub_name}")
        return sub_name
    except Exception as e:
        print(f"Error extracting subtitle: {e}")
        return None



import subprocess

def get_sub_tracks(mkv_file):
    """
    Retrieves the subtitle tracks available in an MKV file using mkvmerge.
    """
    try:
        command = ["mkvmerge", "-i", mkv_file]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            raise Exception(f"Error executing mkvmerge: {result.stderr}")

        sub_tracks = []
        for line in result.stdout.splitlines():
            if "subtitles" in line:
                parts = line.split(":")
                track_id = int(parts[0].split()[-1])
                details = parts[1].strip()
                
                # Attempt to extract the language, if available
                language = "Unknown"
                if "(" in details and ")" in details:
                    parentheses_content = details.split("(")[-1].split(")")[0]
                    if len(parentheses_content) == 3:  # ISO 639-2 format (e.g., "eng", "por")
                        language = parentheses_content
                
                name = (
                    details.replace(f"({language})", "").strip() 
                    if language != "Unknown" 
                    else details
                )
                sub_tracks.append({"id": track_id, "language": language, "name": name})
        return sub_tracks
    except Exception as e:
        print(f"Error listing tracks: {e}")
        return []


def select_sub_tracks(sub_tracks, callback, root):
    """
    Displays a modal window for the user to select a subtitle track.
    After selection, calls the callback with the ID of the selected track.
    """
    import tkinter as tk
    from tkinter import messagebox

    selected_track = tk.StringVar()

    def confirm_selection():
        selected = track_listbox.curselection()
        if not selected:
            tk.messagebox.showwarning(
                "Warning", "No track was selected.", parent=selection_window
            )
            return
        track = sub_tracks[selected[0]]  # Access the dictionary of the selected track
        selected_track.set(track["id"])  # Set the ID of the selected track
        selection_window.destroy()  # Close the window after selection

    # Secondary window to display options
    selection_window = tk.Toplevel(root)
    selection_window.title("Select a Subtitle Track")
    selection_window.iconbitmap("./img/sucata_icon.ico")
    selection_window.geometry("400x300")
    selection_window.configure(bg="#181825")
    selection_window.transient(root)  # Set as a modal window
    selection_window.grab_set()

    label = tk.Label(
        selection_window,
        text="Select the subtitle track to process:",
        bg="#181825",
        fg="white"
    )
    label.pack(pady=10)

    track_listbox = tk.Listbox(
        selection_window,
        bg="#202030",
        fg="#14b83e",
        height=10,
        width=50,
        selectmode=tk.SINGLE
    )
    for track in sub_tracks:
        track_listbox.insert(
            tk.END,
            f"Track {track['id']} - {track['language']} ({track['name']})",
        )
    track_listbox.pack(pady=10)

    confirm_button = tk.Button(
        selection_window,
        text="Confirm",
        command=confirm_selection,
        bg="#1E1E2A",
        fg="white"
    )
    confirm_button.pack(pady=10)

    selection_window.wait_window()

    if selected_track.get():
        callback(selected_track.get())  # Call the callback with the ID of the selected track
    else:
        callback(None)  # No track was selected



def remove_subtitle_formatting(events):
    """
    Removes formatting such as style tags and codes from subtitle events.
    """
    def clean_text(text):
        # Remove tags in { } and < >
        text = re.sub(r"\{.*?\}", "", text)
        text = re.sub(r"<.*?>", "", text)
        return text.strip()

    for event in events:
        event.text = clean_text(event.text)
    return events


def clean_translated_text(translated_text):
    """
    Removes delimiters and any additional content that is not part of the translated text.
    """
    # Check if delimiters are present
    if "<<<Texto a ser traduzido>>>" in translated_text:
        # Extract text between delimiters
        translated_text = translated_text.split("<<<Texto a ser traduzido>>>")[1]
        translated_text = translated_text.split("<<<Fim do texto>>>")[0]

    return translated_text.strip()


def initialize_pipeline(
        model_id="Qwen/Qwen2.5-7B-Instruct"):   # Try "Qwen/Qwen2.5-14B-Instruct" for better quality (High Hardware Costs) # Try "Qwen/Qwen2.5-7B-Instruct" for better balance
    """                                         # Alternative "meta-llama/Llama-3.1-8B-Instruct" or "NousResearch/Hermes-3-Llama-3.1-8B"
    Initializes the text-generation pipeline with the specified model.
    """
    try:
        print("Loading pipeline and automatic device mapping...")
        pipeline = transformers.pipeline(
            "text-generation",
            model=model_id,
            model_kwargs={"torch_dtype": torch.float32}, #float32 has better quality but high cost // float16 has better efficiency but less precision.
            device_map="auto",
        )
        print("Pipeline loaded successfully.")
        return pipeline
    except Exception as e:
        print(f"Error loading pipeline: {e}")
        raise



def translate_events(events, pipeline, source_language, target_language, log_text, progress_bar=None):
    translations = []
    if progress_bar:
        progress_bar["maximum"] = len(events)

    for i, event in enumerate(events):
        # Context: 5 lines before and 5 after
        previous_context = " ".join([e.text for e in events[max(0, i-3):i]])
        next_context = " ".join([e.text for e in events[i+1:min(len(events), i+4)]])

        # Construct the prompt with clear delimiters
        prompt_content = []
        if previous_context:
            prompt_content.append(f"[Previous Context]: {previous_context}")
        prompt_content.append(f"[Text to Translate]: {event.text}")
        if next_context:
            prompt_content.append(f"[Next Context]: {next_context}")
       
        prompt = [
            {
                "role": "system",
                "content": (
                    f"You are a professional subtitle translator specializing in movies, TV series, and anime. Translate from {source_language} to {target_language} following these detailed guidelines:\n\n"
                    f"### Translation Guidelines\n"
                    f"1. **Preserve Meaning and Tone:**\n"
                    f"   - Ensure translations match the original tone (e.g., formal, casual, humorous) and emotional impact.\n"
                    f"   - Avoid literal translations unless they are contextually appropriate.\n"
                    f"   - Reorganize sentences as needed to sound natural and fluent in {target_language}.\n"
                    f"   - Pay attention to nuances, cultural context, and idiomatic expressions.\n\n"
                    f"2. **Context Awareness:**\n"
                    f"   - Use [Previous Context] and [Next Context] to ensure coherent translations.\n"
                    f"   - Resolve ambiguities by prioritizing naturalness over overly specific interpretations.\n"
                    f"   - Adapt cultural references, idioms, and slang to resonate naturally with the target audience.\n\n"
                    f"3. **Technical Accuracy:**\n"
                    f"   - Retain all formatting tags (e.g., {{\\blur}}, {{\\pos}}, {{\\an}}) exactly as they appear.\n"
                    f"   - Interpret '\\N' as a line break and preserve its position.\n"
                    f"   - Ensure translated text respects subtitle constraints, including character limits.\n"
                    f"   - Tags must never be altered, omitted, or repositioned.\n\n"
                    f"4. **Consistency and Quality:**\n"
                    f"   - Maintain consistent terminology and style across translations.\n"
                    f"   - Use verbs and expressions appropriate to the tense, nuance, and tone of the original.\n"
                    f"   - Proofread for grammar, spelling, and punctuation accuracy.\n"
                    f"   - Translate informal or colloquial language contextually, considering the character and scene.\n\n"
                    f"{anime_variable}\n"
                    f"**Final Checklist:**\n"
                    f"   - Is the translation fluent, natural, and free of literal errors?\n"
                    f"   - Are all formatting tags intact and unaltered?\n"
                    f"   - Does the text respect subtitle constraints and character limits?\n"
                    f"   - Were cultural references adapted naturally for the target audience?\n"
                    f"   - Is the output consistent with the original meaning, tone, and context?\n\n"
                )
            },      
            {
                    "role": "user",
                    "content": (
                        f"### Translation Task\n"
                        f"1. Use the provided context below **only if it is available and makes sense for the given text**. Do not include it in the translation itself. The context should be used solely to ensure the translation aligns with the tone and meaning of the scene:\n"
                        f"   - [Previous Context]: {previous_context if previous_context else 'No additional context available.'}\n"
                        f"   - [Next Context]: {next_context if next_context else 'No additional context available.'}\n"
                        f"\n"
                        f"2. Translate only the text below into {target_language}, preserving:\n"
                        f"   - The original tone and meaning.\n"
                        f"   - All formatting tags (e.g., {{\\c&H1010A4&}}, {{\\pos}}, '\\N'). Do not interpret or modify the tags.\n"
                        f"\n"
                        f"3. Important Instructions:\n"
                        f"   - Respond **only** with the translated text for the given line. Do not include any comments, explanations, or attempts to correct the translation.\n"
                        f"   - If the line is ambiguous, provide the best possible translation based solely on the provided line.\n"
                        f"   - If no context is available or the context is irrelevant, translate naturally and accurately.\n"
                        f"\n"
                        f"### Text to Translate:\n"
                        f"{event.text}"
                    )
                }
        ]
        


        try:
            # Generate translation using the pipeline
            output = pipeline(prompt, max_new_tokens=1024)
            print(f"Output for line {i + 1}:\n\nOriginal:{event.text}\n\nTraslated:{output[0]["generated_text"][-1]}")  # Debugging

            # Extract the translation from the output
            if isinstance(output, list):
                messages = output[0].get("generated_text", [])
                if isinstance(messages, list):
                    for message in messages:
                        if message.get("role") == "assistant":
                            translated_text = message.get("content", "").strip()
                            translated_text = clean_translated_text(translated_text)  # Clean delimiters
                            translations.append(translated_text)
                            break
                    else:
                        raise ValueError("No message with 'role': 'assistant' found.")
                else:
                    raise ValueError("Unexpected format in 'generated_text'.")
            else:
                raise ValueError(f"Unexpected output format: {output}")
        except Exception as e:
            log_text.insert(tk.END, f"Error translating event {i + 1}: {e}\n")
            translations.append(event.text)  # Keep the original text in case of error

        # Update progress bar and logs
        if progress_bar:
            progress_bar["value"] += 1
            progress_bar.update()

        if log_text and i % 10 == 0:
            log_text.insert(tk.END, f"Translated {i + 1}/{len(events)} lines...\n")
            log_text.see(tk.END)
            log_text.update()

    return translations



def save_subtitle(subs, output_file):
    try:
        subs.save(output_file)
        print(f"Translated subtitle saved in: {output_file}")
    except Exception as e:
        print(f"Error saving subtitle: {e}")


def process_subtitle(subtitle_file, source_language, target_language, log_text, progress_bar, pipeline):
    try:
        print(f"Processing file: {subtitle_file}")  # Log to check the file
        subs = pysubs2.load(subtitle_file)  # Load the subtitle
        print(f"Number of events loaded: {len(subs)}")  # Verify if events were loaded
        if subtitle_file.endswith(".srt"):
            # Clean formatting
            events = remove_subtitle_formatting([event for event in subs if event.text.strip()])
        elif subtitle_file.endswith(".ass") or subtitle_file.endswith(".ssa"):
            events = [event for event in subs if event.text.strip()]
        else:
            raise ValueError("Unsupported subtitle format.")

        # Translate events
        translations = translate_events(events, pipeline, source_language, target_language, log_text, progress_bar)

        for event, translation in zip(events, translations):
            event.text = translation

        # Save the translated subtitle
        output_file = subtitle_file.replace(".srt", "_translated.srt").replace(".ass", "_translated.ass").replace(".ssa", "_translated.ssa")
        subs.save(output_file)
        print("Translated subtitle successfully saved.")
        return output_file
    except Exception as e:
        print(f"Error processing subtitle: {e}")
        return None
    

def process_file(file, source_language, target_language, log_text, progress_bar):
    if file.endswith(".mkv"):
        # Handle MKV files
        file_output = os.path.dirname(file)
        extracted_subtitle = extract_mkv_sub(file, file_output)
        if extracted_subtitle:
            translated_subtitle = process_subtitle(extracted_subtitle, source_language, target_language, log_text, progress_bar)
            if translated_subtitle and (translated_subtitle.endswith(".ass") or translated_subtitle.endswith(".ssa")):
                output_mkv = os.path.join(file_output, "output_translated.mkv")
                embed_subtitle_in_mkv(file, translated_subtitle, output_mkv)
                log_text.insert(tk.END, f"Processing completed. MKV file saved in: {output_mkv}\n")
            else:
                log_text.insert(tk.END, "Translated SRT subtitle saved separately.\n")
        else:
            log_text.insert(tk.END, "No subtitles extracted from the MKV file.\n")
    elif file.endswith((".srt", ".ass", ".ssa")):
        # Handle subtitle files directly
        translated_subtitle = process_subtitle(file, source_language, target_language, log_text, progress_bar)
        if translated_subtitle:
            log_text.insert(tk.END, f"Translated subtitle saved in: {translated_subtitle}\n")
        else:
            log_text.insert(tk.END, "Error processing the subtitle.\n")
    else:
        log_text.insert(tk.END, "Unsupported file format.\n")


def embed_subtitle_in_mkv(mkv_file, translated_subtitle, output_mkv):
    try:
        mkv = MKVFile(mkv_file)
        mkv.add_track(translated_subtitle)
        mkv.mux(output_mkv)
        print(f"MKV file with translated subtitle saved as: {output_mkv}")
    except Exception as e:
        print(f"Error embedding the subtitle: {e}")



def start_interface():
    # Initialize the pipeline globally
    pipeline = None

    try:
        pipeline = initialize_pipeline()
    except Exception as e:
        print(f"Error initializing the pipeline: {e}")

    def load_file():
        file = filedialog.askopenfilename(
            filetypes=[("Subtitle and MKV Files", "*.srt *.ass *.ssa *.mkv")]
        )
        file_input.delete(0, tk.END)
        file_input.insert(0, file)

    def start_processing():
        # Processing function in a separate thread
        def task():
            try:
                # Disable the button while processing
                btn_start.config(state=tk.DISABLED)
                progress_bar.config(mode="indeterminate")
                progress_bar.start()
                loading_label.config(text="Processing...")

                # Retrieve values from the interface
                file = file_input.get()
                source_language = dropdown_source_language.get() if dropdown_source_language.get() else None
                target_language = dropdown_target_language.get() if dropdown_target_language.get() else None

                if not file:
                    log_text.insert(tk.END, "Please select a file.\n")
                    return
                if not source_language:
                    log_text.insert(tk.END, "Please select the source language.\n")
                    return

                # Decide what to do based on the file type
                if file.endswith(".mkv"):
                    def process_track(selected_track):
                        if selected_track:
                            track_id = int(selected_track)
                            file_output = os.path.dirname(file)
                            extracted_subtitle = extract_mkv_sub(file, file_output, track_id)
                            if extracted_subtitle:
                                translated_subtitle = process_subtitle(
                                    extracted_subtitle,
                                    source_language,
                                    target_language,
                                    log_text,
                                    progress_bar,
                                    pipeline,
                                )
                                if translated_subtitle:
                                    output_mkv = os.path.join(file_output, "output_translated.mkv")
                                    embed_subtitle_in_mkv(file, translated_subtitle, output_mkv)
                                    log_text.insert(tk.END, f"Processing completed. MKV file saved in: {output_mkv}\n")
                                else:
                                    log_text.insert(tk.END, "Error processing the subtitle.\n")
                            else:
                                log_text.insert(tk.END, "Error extracting the selected subtitle.\n")
                        else:
                            log_text.insert(tk.END, "No track selected.\n")

                    sub_tracks = get_sub_tracks(file)
                    if sub_tracks:
                        select_sub_tracks(sub_tracks, process_track, root=window)
                    else:
                        log_text.insert(tk.END, "No subtitle tracks found in the MKV file.\n")

                elif file.endswith((".srt", ".ass", ".ssa")):
                    # Process subtitle files directly
                    log_text.insert(tk.END, "Processing subtitle...\n")
                    translated_subtitle = process_subtitle(
                        file, source_language, target_language, log_text, progress_bar, pipeline
                    )
                    if translated_subtitle:
                        log_text.insert(tk.END, f"Translated subtitle saved in: {translated_subtitle}\n")
                    else:
                        log_text.insert(tk.END, "Error processing the subtitle.\n")
                else:
                    log_text.insert(tk.END, "Unsupported file format.\n")

            except Exception as e:
                log_text.insert(tk.END, f"Error during processing: {e}\n")
            finally:
                # Re-enable the button and stop the progress bar
                btn_start.config(state=tk.NORMAL)
                progress_bar.stop()
                progress_bar.config(mode="determinate")
                loading_label.config(text="")

        # Create and start the thread
        thread = threading.Thread(target=task)
        thread.start()

    # Interface setup
    window = tk.Tk()
    window.title("Sucata")
    window.geometry("400x850")
    window.configure(bg="#181825")
    window.iconbitmap("img/sucata_icon.ico")

    title_font = ImageFont.truetype("fonts/Horizon.otf", size=24)
    subtitle_font = ImageFont.truetype("fonts/FKGroteskNeueTrial-Bold.otf", size=18)

    def create_text_image(text, width, height, font, bg_color, text_color):
        """Creates a stylized text image using Pillow."""
        img = Image.new("RGBA", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((width - w) // 2, (height - h) // 2), text, justify="center", font=font, fill=text_color)
        return ImageTk.PhotoImage(img)

    image = Image.open("img/sucata_hello.png")
    image = image.resize((150, 150))
    image_tk = ImageTk.PhotoImage(image)
    img_label = tk.Label(window, image=image_tk, bg="#181825")
    img_label.image = image_tk
    img_label.pack(pady=(20, 0))

    title_img = create_text_image(
        "Hello, I'm Sucata.", 400, 30, title_font, bg_color="#181825", text_color="white"
    )
    title_label = tk.Label(window, image=title_img, bg="#181825")
    title_label.image = title_img
    title_label.pack(pady=(5, 7))

    subtitle_img = create_text_image(
        "I am a subtitle translator\nusing Open-Source A.I.",
        400,
        70,
        subtitle_font,
        bg_color="#181825",
        text_color="white",
    )
    subtitle_label = tk.Label(window, image=subtitle_img, bg="#181825")
    subtitle_label.image = subtitle_img
    subtitle_label.pack(pady=(0, 5))

    lbl_file = tk.Label(window, text="Insert a subtitle file:", bg="#181825", fg="white")
    lbl_file.pack()
    file_input = tk.Entry(window, width=50)
    file_input.pack()
    btn_load = tk.Button(window, text="Select File", command=load_file, bg="#1E1E2A", fg="white")
    btn_load.pack(pady=10)

    lbl_source_language = tk.Label(window, text="Source Language:", bg="#181825", fg="white")
    lbl_source_language.pack()
    available_languages = [
        "ar - Arabic",
        "bn - Bengali",
        "de - German",
        "en - English",
        "es - Spanish",
        "fr - French",
        "hi - Hindi",
        "id - Indonesian",
        "ja - Japanese",
        "ko - Korean",
        "lah - Western Punjabi",
        "mr - Marathi",
        "pt - Portuguese",
        "pt-BR - Brazilian Portuguese",
        "ru - Russian",
        "ta - Tamil",
        "te - Telugu",
        "tr - Turkish",
        "ur - Urdu",
        "vi - Vietnamese",
        "zh - Mandarin Chinese"
    ]
    dropdown_source_language = ttk.Combobox(window, values=available_languages, width=30)
    dropdown_source_language.pack(pady=(0, 10))
    dropdown_source_language.set("en - English")

    lbl_target_language = tk.Label(window, text="Target Language:", bg="#181825", fg="white")
    lbl_target_language.pack()
    dropdown_target_language = ttk.Combobox(window, values=available_languages, width=30)
    dropdown_target_language.pack(pady=(0, 20))
    dropdown_target_language.set("pt-BR - Brazilian Portuguese")

    def change_AnimeMode():
        global anime_variable  
        if checkbox_AnimeMode.get():
            anime_variable = (
                "5. **Anime Mode:** Ensure translations adapt slang, honorifics, and cultural nuances for an audience familiar with otaku, nerd, and geek culture.\n"
                f"   - Retain key otaku/geek/nerd terms (e.g., 'senpai,' 'baka,' 'itadakimasu,' 'OP,' 'Overpower') only if they are essential to the context or carry cultural significance that cannot be translated effectively.\n"
                f"   - When retaining Japanese terms, provide clarity through the surrounding text if necessary.\n"
                f"   - Adapt expressions to natural equivalents when the cultural reference is not critical for understanding or impact.\n"
                f"   - Example:\n"
                f"     - Original: 'You’re such a baka!'\n"
                f"     - Translation: 'Você é tão idiota!' (but retain 'baka' if it adds cultural or emotional nuance).\n"
                f"     - Original: 'Itadakimasu!'\n"
                f"     - Translation: Retain 'Itadakimasu' if addressing an otaku audience, or adapt as 'Bom apetite!' for general audiences.\n\n"
                f"   - Maintain honorifics (e.g., 'san,' 'kun,' 'chan') only if they add context or convey relationships and hierarchy important to the story. Otherwise, adapt to natural equivalents.\n"
                f"   - Preserve the tone and style typical of anime dialogue (e.g., exaggerated expressions, comedic timing, or dramatic intensity).\n"
                f"   - Avoid over-translating technical terms, catchphrases, or culturally embedded phrases; instead, consider footnotes or additional contextual cues if critical for understanding.\n"
            )
        else:
            anime_variable = ""  

    # Inside your start_interface function:
    checkbox_AnimeMode = tk.BooleanVar()  # Variable linked to Anime Mode checkbox
    checkbox_AnimeMode.set(False)  # Default state: not checked

    # Create the Anime Mode Checkbutton
    animeMode = tk.Checkbutton(
        window,
        text="Anime Mode",
        variable=checkbox_AnimeMode,
        onvalue=True,
        offvalue=False,
        command=change_AnimeMode,
        bg="#181825",
        fg="#14b83e"
    )
    animeMode.pack(pady=10)  # Ensure the checkbox is displayed

    btn_start = tk.Button(window, text="Start Translation", command=start_processing, bg="#1E1E2A", fg="white")
    btn_start.pack()

    progress_bar = ttk.Progressbar(window, length=400, mode="determinate")
    progress_bar.pack(pady=10)

    loading_label = tk.Label(window, text="", bg="#181825", fg="white")
    loading_label.pack()

    log_text = tk.Text(window, height=10, wrap="word", bg="#202030", fg="#14b83e", insertbackground="white")
    log_text.pack()

    footer_label = tk.Label(window, text="Developed with ❤️\nby Pedro Guina Saltareli.", font=("Courier New", 10), fg="white", bg="#181825")
    footer_label.pack(pady=5)

    window.mainloop()


if __name__ == "__main__":
    start_interface()