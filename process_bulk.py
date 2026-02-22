import re
import pathlib
import sys
import glob
import polars

"""Program that will preprocess raw script files `file.txt` and obtain all function calls with dialogue, which it will store into a json file. Files to be 
preprocessed will be passed in via arguments. Provide a chapter name appended with colon, which will concatenate all script files in a directory or files 
to be inside that chapter. Multiple chapters can be processed at once this way.

program :<chapter_name> <dir1> [dir2 file1 file2] [:<chapter2_name> <dir3> [dir4 dir5 file3] ...]
"""

interactive = True

chapter = polars.DataFrame(
    schema={
        "Day": polars.String,               # Higurashi has 8 chapters, commonly referred to as 'arcs' (such as Onikakushi [Ch1] or Meakashi[Ch5]). Each of
                                            # these chapters are further divided into subchapters, commonly referred to as 'days'. It is usually the name 
                                            # of the file, indicating the day within a particular chapter.
                                            #
                                            # Range: Non-empty string.

        "LineNo": int,                      # ID number of a particular line that is said in a particular subchapter. Each ID is unique and incremental.
                                            #
                                            # Range: Integer > 0

        "JP_Speaker": polars.String,        # Text representing the name of the character speaking in Japanese. If there is no associated speaker, this 
                                            # will be empty. 
                                            #
                                            # Range: A small Japanese text string or empty.

        "EN_Speaker": polars.String,        # Text representing the name of the character speaking in English. If there is no associated speaker, this 
                                            # will be empty. 
                                            #
                                            # Range: A small string or empty.

        "JP_Text": polars.String,           # The actual dialogue text in Japanese. 
                                            #
                                            # Range: Non-empty Japanese string

        "EN_Text": polars.String,           # The actual dialogue text in English. 
                                            #
                                            # Range: Non-empty string.

        "Spacing": polars.String,           # Formatting information for how the text should be displayed, including line breaks and spacing. TODO

        "CensorshipLevel": int              # The highest censorship level at which this dialogue can be seen. If current censorship level is higher
                                            # than this value, this dialogue should not be presented. For censored text, the same line may be typically 
                                            # represented by multiple texts, each with a different censorship level. Any ONE of these should be rendered, 
                                            # which is the lowest number greater than or equal to current censorship level.
                                            # 
                                            # Range: Integer [0-5]
                                            # Majority of the text in this dataset is at level 5, with the most explicit scenes happening at lower levels 
                                            # like 2 or 1.
    }
)

def append_to_dataframe(i, line, speaker, day, spacing, censor_level):
    global chapter
    if speaker == None:
        speaker = (None, None)

    df = polars.DataFrame(
        {
            "Day": day,
            "LineNo": i,
            "JP_Speaker": speaker[0],
            "EN_Speaker": speaker[1],
            "JP_Text": line[0],
            "EN_Text": line[1],
            "Spacing": spacing,
            "CensorshipLevel": censor_level
        }
    )
    chapter.vstack(df, in_place=True)

def change_lastentry_spacing(spacing):
    global chapter
    if chapter.is_empty():
        return

    last_row = chapter[-1]
    chapter = chapter[:-1]
    append_to_dataframe(
                        last_row["LineNo"].item(), 
                        (last_row["JP_Text"].item(), last_row["EN_Text"].item()),
                        (last_row["JP_Speaker"].item(), last_row["EN_Speaker"].item()),
                        last_row["Day"].item(),
                        spacing, 
                        last_row["CensorshipLevel"].item()
                        )

def is_japanese_text(text):
    """
    Checks if a string contains Japanese characters (Hiragana, Katakana, or Kanji).

    Args:
    text: The string to check.

    Returns:
    True if the string contains Japanese characters, False otherwise.
    """
    japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
    return bool(japanese_pattern.search(text))

def load_file_to_dataframe(filestr, filename, lineno=0, censor_level=5, filepath=None, current_speaker=None):
    pattern_CensorshipCode = r'if\s*\(GetGlobalFlag\(GCensor\)\s*(?:>=|<=)\s*\d+\)\{\s*ModCallScriptSection\("[^"]+",\s*"[^"]+"\);\s*\}'    # we heavily use /s* to capture any number of whitespace chars that may exist between text elements
    pattern_OutputLineAll = r"OutputLineAll\s*\([\s\S]*?\);"
    pattern_OutputLine = r"OutputLine\s*\([\s\S]*?\);"

    pattern_SD_size = r'OutputLine\(NULL,\s*"",\s*NULL,\s*"<size=[-+]?\d+>",\s*Line_Continue\);'

    #print(r"%s|%s|%s" % (pattern_OutputLine, pattern_OutputLineAll, pattern_CensorshipCode))
    matcher_commands = re.compile(r"%s|%s|%s" % (pattern_OutputLine, pattern_OutputLineAll, pattern_CensorshipCode))    # broken to make debugging easier
    matcher_dialogues = re.compile(r'\"(.*)\"') # greedy, will end up catching things like `"<color=#f5e6d3>圭一の母</color>", NULL, "<color=#f5e6d3>Keiichi's mom</color>"` as one string
    matcher_colortag = re.compile(r'<color=[^>]+>([^<]+)<\/color>')
    matcher_GADVoutputline = re.compile(r'OutputLineAll\s*\(\s*\"\"\s*,\s*NULL\s*,')
    matcher_nonGADVGoutputline = re.compile(r'OutputLineAll\s*\(\s*NULL\s*,\s*\"(\\n)*\"|OutputLineAll\s*\(\s*NULL\s*,\s*\"(\s)*\"')
    matcher_CensorshipCodeJump = re.compile(r'if\s*\(GetGlobalFlag\(GCensor\) (>=|<=) (\d+)\)\{ModCallScriptSection\("([^"]+)","([^"]+)"\);\}')
    matcher_SpecialDirectives = re.compile(r"%s" % (pattern_SD_size)) 

    censorship_state = [lineno, lineno, None]                                        # (i, filename): contains the last position `i` where script jumped to insert text from `filename``.
    if filename == '':
        raise ValueError("Must provide a file name or can't decide subchapter name!")
    ls_dialogueCommands = re.findall(matcher_commands, filestr)    # find all OutputLine commands, these contain the text

    # for d in ls_dialogueCommands:
    #     print(d)
    for d in ls_dialogueCommands:    
        #if i == 4:  # debug
        #    break
        if (re.search(matcher_SpecialDirectives, d) != None):
            # There may be certain commands of OutputLine/All that can be used to manipulate the script, for example 
            # making the font size smaller or larger, or making text red. Our table can't handle this data, so we are ignoring it for now. 
            continue
        if (re.search(matcher_nonGADVGoutputline, d) != None):
            change_lastentry_spacing("\n"*(d.count("\n")+1))

            continue
        elif (re.search(matcher_GADVoutputline, d) != None):
            # this resets the speaker
            current_speaker = None
            continue
        elif (re.search("ModCallScriptSection", d) != None):
            # due to censorship changes, the game script will at times jump to other files, so we must grab all dialogue 
            # within those files AS PART OF THE CURRENT DAY/FILE, without 
            censorship = re.findall(matcher_CensorshipCodeJump, d)[0]
            if (len(censorship) != 4):
                raise ValueError("Unexpected Script Jump string at {}: caused at {}:{}".format(d, (filename if filepath is None else filepath), lineno))
            
            if filepath is not None:
                if not filepath.is_dir():
                    filepath = filepath.parent

            subscript_file = pathlib.Path(filepath, censorship[2]+".txt")
            if not subscript_file.is_file():
                subscript_file = pathlib.Path(input("The file {}.txt is needed but was not found. Please provide the path for this file: ".format(censorship[2])))
                if not subscript_file.is_file():
                    raise RuntimeError("File not found! '{}' is needed to correctly produce the dialogues from script".format(censorship[2]))
            
            subscript_file = open(subscript_file, "r", encoding="utf-8-sig")
            
            # decide censorship level of text
            clevel = None
            if (censorship[0] == '>=' or censorship[0] == '>'):
                # unbounded positively, so this means its ok for levels k and higher (so also ok for level 5)
                # so just set it to 5
                clevel = 5
            elif (censorship[0] == '<=' or censorship[0] == '<'):
                clevel = int(censorship[1])
            else:
                raise Exception("wut the heck la? why is there a different symbol in the censorship check?")

            # partitioning: a file will contain multiple entrypoints, only pass the entrypoint demarcated in the function call
            subscript_filestr = subscript_file.read()
            pattern_ScriptJump = re.compile(r'void\s+' + censorship[3] + r'\(\)\s*\{((?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*)\}')
            m = re.search(pattern_ScriptJump, subscript_filestr)
            if (m == None):
                raise ValueError("Invalid file content in {}: {} entrypoint was not found!".format(censorship[2], censorship[3]))
            subscript_filestr = m.groups()[0]
            #print(subscript_filestr)

            if (censorship_state[2] == censorship[3]):       # read in this subscript file into the current position+day
                # same entrypoint as before! use state to decide lineno, and ensure you don't wipe out previous lineno

                # SERIOUS: turns out different censorship files can have different number of lines, ... well this is a problem. looks like numbers may no longer be purely incremental
                censorfile_lineno = load_file_to_dataframe(subscript_filestr, filename, lineno=censorship_state[0], censor_level=clevel, current_speaker=current_speaker) 
                censorship_state[1] = max(lineno, censorfile_lineno)# store current index so if we need to insert multiple censorship positions we can remember them
                lineno = censorship_state[1]
            else:
                # new entrypoint, change lineno to current linecounter
                censorfile_lineno = load_file_to_dataframe(subscript_filestr, filename, lineno=lineno, censor_level=clevel, current_speaker=current_speaker)
                censorship_state = [lineno, censorfile_lineno, censorship[3]] # store current index so if we need to insert multiple censorship positions we can remember them
                lineno = censorfile_lineno

            subscript_file.close()
            # print(censorship_state)
            continue
            
        res = re.findall(matcher_dialogues, d)

        #print(d)
        if (len(res) > 2):  
            raise ValueError("Unexpected dialogue string at {}: caused at {}:{}".format(d, (filename if filepath is None else filepath), lineno))
        elif len(res) == 2:
            # result contains ("jp text", "eng text")
            # TODO: remove character constants if they exist
            lineno += 1
        elif len(res) == 1:
            #print("I think this part here is a speaker, ... ", res)
            # speaker tag, confirm
            if res[0].find("color") == -1:
                raise ValueError("Unexpected dialogue string at {}: caused at {}:{}".format(d, (filename if filepath is None else filepath), lineno))
            
            speaker = re.findall(matcher_colortag, res[0])
            if (len(speaker) > 2):  
                #continue # we won't append this, test purposes
                # turns out very rarely, a line can have multiple speakers!!!
                if len(speaker) % 2 == 0:  ## expecting n-pairs of japanese,english text
                    print("### Warning: Special exception passthrough at {}:{}, an abnormal dialogue string with multiple speakers are being handled by joining them. Speaker tuple: {}".format(filename, lineno, speaker))
                    current_speaker = [None, None]
                    current_speaker[0] = '_'.join(speaker[:len(speaker)//2])
                    current_speaker[1] = '_'.join(speaker[len(speaker)//2:])
                else:   # abnormal speaker structure, must be handled manually (lets hope this never happens xd)
                    print("### Warning: Special exception passthrough at {}:{}, a special case is being handled for an abnormal dialogue string with uneven speakers, this may be subject to change if the script is modified in the future. Speaker tuple: {}".format(filename, lineno, speaker))
                    # unfortunately this does happen... First hardcoded exception is at Watanagashi:1308
                    if (lineno == 1308) and 'wata_005' in filename: # wierd line with 1 speaker in jp but 2 speakers in EN
                        current_speaker[0] = '_'.join(speaker[:1])
                        current_speaker[1] = '_'.join(speaker[1:])
                    else:
                        raise ValueError("No special case handled for an unexpected dialogue string at {}: caused at {}:{}".format(d, (filename if filepath is None else filepath), lineno))
            elif len(speaker) == 2: # Speaker, classify correctly
                current_speaker = speaker
            elif len(speaker) == 1:
                # TODO: fix wierd edge case where a line only has jp speaker+text
                print("### Warning: Special exception passthrough at {}:{}, an abnormal dialogue string only has one language. Speaker tuple: {}".format(filename, lineno, speaker))
                current_speaker = [None, None]
                if is_japanese_text(speaker[0]):
                    current_speaker[0] = speaker[0]
                else:  # assume english if not japanese
                    current_speaker[1] = speaker[0]

                # how do we catch other failures?
                #raise ValueError("Unexpected dialogue string at {}: caused at {}:{}".format(d, (filename if filepath is None else filepath), lineno))
            continue
            
        # TODO: jump to censorship calls cause current speaker information to be lost (as the function sets current_speaker to None.)

        # clean trailing/leading spaces
        res = (res[0].strip().replace(r'\"', '"'), res[1].strip().replace(r'\"', '"'))

        #print(res[-1], end=' ')    # Outputline apparently pads a space to the end of every sentence by default
        append_to_dataframe(lineno, res, current_speaker, filename, "", censor_level) # every normal dialogue is censorship level 5

    return lineno

def process_chapter(args):
    chapter_output_filename = args[0][1:]
    args = [pathlib.Path(f) for f in args[1:]]
    files_to_process = [path for path in args if path.is_file()]

    for p in args:
        if p.is_dir():
            for f in p.rglob("*.txt"):
                #temp = p.joinpath(f) 
                skip_files = set(["dummy", "flow", "init", 'kakera_miss'])

                if (f.is_file()):
                    if f not in files_to_process:
                        #if not (f.stem[0] == 'z'): # censorship insert, dialogues contained in these files are inserted when a call is made that jumps to this file
                        if ('z' not in f.stem) and ('vm' not in f.stem) and ('&' not in f.stem) and not any(s in f.stem for s in skip_files):
                            files_to_process.append(f)
                else:
                    # wtf is this thing?
                    print(f)
                    raise RuntimeError("How dahecc is this file non-existing and also the result of an glob?")

    print("Will be processing the following files: ")
    for f in files_to_process:
        print("\t{}".format(f))
    
    if (interactive):
        print("Press Enter to continue...")
        input()

    for fn in files_to_process:
        with open(fn, "r", encoding="utf-8-sig") as f:
            chaptername = f.name.rsplit('.')[0]

            lines = load_file_to_dataframe(f.read(), chaptername, filepath=fn)
            print("  -> Grabbed {} lines from {}".format(lines, chaptername))

    #chapter_output_filename = input("Please enter the name of this chapter: ")
    chapter.write_ndjson("{}.json".format(chapter_output_filename))

args = sys.argv[1:]
chapters_and_files = []
try:
    for s in args:
        if s == '-a' or s == '--auto':
            interactive = False
        if s[0] == ':':
            chapters_and_files.append([s])
        else:
            chapters_and_files[-1].append(s)
except: 
    raise Exception("Wrong arguments! Please provide a chapter name for every files to be processed.")

for a in chapters_and_files:
    process_chapter(a)