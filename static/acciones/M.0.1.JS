const botonMicrofono = document.getElementById("microfono");
const audioReproducir = document.getElementById("audioReproducir");
const transcripcionDiv = document.getElementById("transcripcion");

let grabando = false;
let mediaRecorder;
let chunks = [];
let tiempoSilencio = 3000; // 3 segundos
let temporizadorSilencio;
let audioContext;
let analyser;
let source;
let scriptProcessor;

// Configurar conexión WebSocket
const socket = io();

// Escuchar eventos de WebSocket para iniciar o detener la grabación
socket.on("iniciar_grabacion", (data) => {
  console.log(data.message);
  iniciarGrabacion();
});

socket.on("detener_grabacion", (data) => {
  console.log(data.message);
  detenerGrabacion();
});

// Manejo del botón de grabación
botonMicrofono.addEventListener("click", async () => {
  if (grabando) {
    detenerGrabacion();
  } else {
    iniciarGrabacion();
  }
});

// Función para iniciar la grabación
async function iniciarGrabacion() {
  try {
    const beep = new Audio("/static/audios/beep2.mp3");
    beep.play().catch(err => console.error("Error al reproducir beep2:", err));
    
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunks.push(e.data);
      }
    };

    mediaRecorder.onstop = async () => procesarAudio();

    mediaRecorder.start();
    grabando = true;
    botonMicrofono.classList.add("grabando");
    botonMicrofono.innerHTML = "<box-icon name='microphone'></box-icon>";

    // Configurar AudioContext y AnalyserNode para detectar silencio
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    analyser.fftSize = 2048;

    scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);
    analyser.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    scriptProcessor.onaudioprocess = () => {
      const array = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(array);
      const amplitud = array.reduce((a, b) => a + b) / array.length;

      if (amplitud > 10) { // Ajusta este umbral según sea necesario
        reiniciarTemporizadorSilencio();
      }
    };

    // Iniciar el temporizador de silencio
    reiniciarTemporizadorSilencio();
  } catch (error) {
    alert("Error al acceder al micrófono: " + error.message);
    console.error(error);
  }
}

// Función para detener la grabación
function detenerGrabacion() {
  const beep = new Audio("/static/audios/beep.mp3");
  beep.play().catch(err => console.error("Error al reproducir beep:", err));
  if (mediaRecorder && grabando) {
    mediaRecorder.stop();
    grabando = false;
    botonMicrofono.classList.remove("grabando");
    botonMicrofono.innerHTML = "<box-icon name='microphone-off'></box-icon>";

    clearTimeout(temporizadorSilencio); // Limpiar el temporizador

    // Liberar recursos de AudioContext
    if (audioContext) {
      audioContext.close();
      audioContext = null;
    }
  }
}

// Función para procesar el audio
async function procesarAudio() {
  const blob = new Blob(chunks, { type: "audio/webm" });
  const url = URL.createObjectURL(blob);
  audioReproducir.src = url;
  chunks = [];

  const formData = new FormData();
  formData.append("audio", blob, "audio.webm");

  try {
    const response = await fetch("/audio", { method: "POST", body: formData });
    const result = await response.json();

    if (result.text) {
      transcripcionDiv.textContent = `Texto transcrito: ${result.text}`;
    } else {
      transcripcionDiv.textContent = `Error en la transcripción: ${result.error}`;
    }
  } catch (error) {
    transcripcionDiv.textContent = "Error al enviar el audio al servidor.";
    console.error(error);
  }
}

// Función para reiniciar el temporizador de silencio
function reiniciarTemporizadorSilencio() {
  clearTimeout(temporizadorSilencio); // Limpiar el temporizador anterior
  temporizadorSilencio = setTimeout(() => {
    console.log("Silencio detectado. Enviando solicitud para detener grabación.");
    socket.emit("detener_grabacion", { message: "Detener grabación por 3 segundos de silencio" });
    detenerGrabacion();
  }, tiempoSilencio); // 3 segundos
}

