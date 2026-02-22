// consider implementing voice and 
///// Settings
let GATHER_SAME_SPEAKER_DIALOGUE = true;

// Global Vars
SUBCHAPTER_TEXT = 'onikakushi\\onik_001';



function lookup_SpeakerColors(speakername) {
  var tables = {
    "Rena": "#F19A4F",
    "Akasaka": "#393C43",
    "Ooishi": "#98909B",
    "Keiichi": "#956f6e",
    "Mion": "#5ec599",
    "Shion": "#5ec599",
    "Satoko": "#fbda77",
    "Rika": "#6972c0"
  };

  if (tables.hasOwnProperty(speakername))
    return tables[speakername];
  else
    return "#f5e6d3";        // side chars 
}

function parseAndInsertParagraph(textstr)
{
  console.log(textstr)
  contents = textstr.split('\n');

  var p = null; // current paragraph
  for (var i = 0; i < contents.length; i++) {
    if (contents[i].length > 2)
      var gametextdb = JSON.parse(contents[i]);

    console.log(gametextdb)
    // test: insert only himatsubushi day 4
    if (gametextdb.Day != SUBCHAPTER_TEXT) {
      //console.log(gametextdb);
      p = makeParagraph(p, gametextdb.EN_Speaker, gametextdb.EN_Text, gametextdb.Spacing);
      appendParagraph('textlog_dialoguecontainer', p);
    }
  }
}

function readFile(file) {  // this is probably a useless function :L
  if (!file) {
    return;
  }
  clearParagraph('textlog_dialoguecontainer');

  var reader = new FileReader();
  reader.onload = function (e) {  // what to do when the filereader reads a file
    var contents = e.target.result;
    parseAndInsertParagraph(contents);
  };

  reader.readAsText(file);    // start reading  the file
}

function readBlob(blob) {
  if (!blob) {
    return;
  }

  clearParagraph('textlog_dialoguecontainer');
  
  var textstr = blob.text();   // this will probably cause a problem cause this returns a promise.

  parseAndInsertParagraph(textstr);
}

function makeParagraph(prevPara, speaker, text, spacing) {
  var p = document.createElement("p");
  if (speaker)
    try {
      var isSameSpeaker = prevPara.querySelector("span.speaker").textContent == speaker;
    } catch (error) { // span doesnt exist.
      var isSameSpeaker = false;
    }
  else
    var isSameSpeaker = false;  // never gather speakerless text unless ...

  if (prevPara && GATHER_SAME_SPEAKER_DIALOGUE && isSameSpeaker)
    var p = prevPara;

  if (speaker && !isSameSpeaker) { // new speaker span insertion
    const span = document.createElement("span");
    span.className = "speaker";
    span.style.color = lookup_SpeakerColors(speaker);
    span.textContent = speaker;
    p.appendChild(span);
    p.appendChild(document.createElement("br"));
  }
  if (spacing != '')
    console.log("wow! spacing exists!!!");
  
//  text = preprocess_scripttext(text);        // TODO: we wanna manually parse all tags and implement the effects ourselves (the script contains wierd tags that dont exist in html like <size>, etc.)

  //p.appendChild(document.createTextNode(text + ' ' + spacing));  // safe but this ended up escaping the html tags in the script (ex: tsumihoroboshi)
  p.innerHTML += text + ' ' + spacing;        

  return p;
}

function appendParagraph(targetId, para) {
  const target = document.getElementById(targetId);

  target.appendChild(para);
}

function clearParagraph(targetId) {
  const target = document.getElementById(targetId);

  target.textContent = '';
}

async function getChapterData(chapter) {
  // Check localStorage first
  const cached = localStorage.getItem(`chapter_${chapter}_db`);
  if (cached) {
    return JSON.parse(cached);
  }

  // Otherwise, fetch and store it
  const response = await fetch(`/data/${chapter}.json`);
  if (!response.ok)
    throw new Error("Failed to load chapter data");

  const data = await response.json();
  localStorage.setItem(`chapter_${chapter}_db`, JSON.stringify(data));
  return data;
}

// needed cause we need progress bar
async function downloadWithProgressXHR(url, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.responseType = "blob";

    xhr.onprogress = function (event) {
      if (event.lengthComputable) {
        onProgress(event.loaded / event.total);
      }
    };

    xhr.onload = function () {
      if (xhr.status === 200) {
        resolve(xhr.response);
      } else {
        reject(new Error(`HTTP ${xhr.status}: Couldn't download file ${url}`));
      }
    };

    xhr.onerror = reject;
    xhr.send();
  });
}


/* 
 * (class)Progress<nowValue, minValue, maxValue>
 */

//helper function-> return <DOMelement>
function elt(type, prop, ...childrens) {
  let elem = document.createElement(type);
  if (prop) Object.assign(elem, prop);
  for (let child of childrens) {
    if (typeof child == "string") elem.appendChild(document.createTextNode(child));
    else elem.appendChild(elem);
  }
  return elem;
}

//Progress class: min and max should typically be 0 and 100% (because these directly control width as percentage)
class Progress {
  constructor(now, min, max, options) {
    this.dom = elt("div", {
      className: "progress-bar"
    });
    this.min = min;
    this.max = max;
    this.intervalCode = 0;
    this.now = now;
    this.syncState();
    if (options.parent) {
      document.querySelector(options.parent).appendChild(this.dom);
    }
    else document.body.appendChild(this.dom)
  }

  syncState() {
    this.dom.style.width = this.now + "%";
  }

  // increments progress bar by `step` every `time` milliseconds
  startTo(step, time) {
    if (this.intervalCode !== 0) return;
    this.intervalCode = setInterval(() => {
      //console.log("sss")
      if (this.now + step > this.max) {
        this.now = this.max;
        this.syncState();
        clearInterval(this.interval);
        this.intervalCode = 0;
        return;
      }
      this.now += step;
      this.syncState()
    }, time)
  }

  // increments progress bar by `step`. This should be called on a loop
  updateProgress(step) {
    if (this.now + step > this.max) {
      this.now = this.max;
      this.syncState();
      clearInterval(this.interval);
      this.intervalCode = 0;
      return;
    }
    this.now += step;
    this.syncState()
  }

  // sets progress bar to `current`. 
  setProgress(current) {
    if (current > this.max) {
      this.now = this.max;
    }
    else if (current < this.min) {
      this.now = this.min;
    }

    this.now = current;
    this.syncState();
    clearInterval(this.interval);
    this.intervalCode = 0;
    return;
  }

  getProgress(current) {
    return this.now;
  }

  isComplete() {
    return this.getProgress == this.max;
  }

  end() {
    this.setProgress(this.max);
  }

  reset() {
    this.setProgress(this.min);
  }
}

// Example usage
// downloadWithProgressXHR("/bigfile.json", progress => {
//     console.log(`Progress: ${(progress * 100).toFixed(2)}%`);
// }).then(blob => {
//     console.log("Download complete!", blob);
// });


function main() {
  // param time
  const params = new URLSearchParams(window.location.search);
  const chapterName = params.get("chapter");

  // if no args,
  if (!chapterName)
  {
    document.getElementById('loading_icon_container').innerText = "No chapter to load!";
    throw new Error("No chapter to load!");
  }
  
  // start progress bar
  let pb = new Progress(0, 0, 100, { parent: ".loading_icon" });
  
  downloadWithProgressXHR(`../${chapterName}.json`, progress => {
    console.log(`Downloading file... Progress: ${(progress * 100).toFixed(2)}%`);
    pb.setProgress(progress * 100);
  }).then(blob => {
    readBlob(blob);
  });
}


main()
