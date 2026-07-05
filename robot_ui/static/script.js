document.addEventListener("DOMContentLoaded", () => {
    const homeScreen = document.getElementById("home-screen");
    const voiceScreen = document.getElementById("voice-screen");
    const startVoiceBtn = document.getElementById("start-voice-btn");
    const backBtn = document.getElementById("back-btn");

    const voiceContainer = document.querySelector(".voice-interface-container");
    const micToggleBtn = document.getElementById("mic-toggle-btn");
    const voiceStatus = document.getElementById("voice-status");
    const transcriptText = document.getElementById("transcript-text");

    let isListening = false;
    let currentAudio = null;
    let activeRecognition = null;
    let mediaStream = null;
    let audioContext = null;
    let audioSource = null;
    let audioProcessor = null;
    let recordedChunks = [];
    let recordingSampleRate = 44100;

    const adminBtn = document.getElementById("admin-btn");
    const medBtn = document.getElementById("med-btn");

    const passwordModal = document.getElementById("password-modal");
    const passInput = document.getElementById("admin-password");
    const confirmPassBtn = document.getElementById("confirm-pass-btn");
    const cancelPassBtn = document.getElementById("cancel-pass-btn");

    const medModal = document.getElementById("med-modal");
    const medYesBtn = document.getElementById("med-yes-btn");
    const medNoBtn = document.getElementById("med-no-btn");
    const closeMedBtn = document.getElementById("close-med-btn");

    startVoiceBtn.addEventListener("click", () => {
        homeScreen.classList.remove("active");
        voiceScreen.classList.add("active");
        voiceStatus.textContent = "Nhấn micro để bắt đầu nói.";
        transcriptText.textContent = "";
    });

    backBtn.addEventListener("click", () => {
        stopCurrentAudio();
        stopListeningState(false);
        voiceScreen.classList.remove("active");
        homeScreen.classList.add("active");
    });

    micToggleBtn.addEventListener("click", () => {
        if (isListening) stopListeningState();
        else startListeningState();
    });

    adminBtn.addEventListener("click", () => {
        passwordModal.classList.add("show");
        passInput.value = "";
        passInput.focus();
    });

    cancelPassBtn.addEventListener("click", () => {
        passwordModal.classList.remove("show");
    });

    confirmPassBtn.addEventListener("click", () => {
        const password = passInput.value;

        if (password === ADMIN_PASSWORD) {
            passwordModal.classList.remove("show");
            window.location.assign("/admin");
        } else {
            alert("Mật khẩu không đúng!");
            passInput.value = "";
        }
    });

    passInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            confirmPassBtn.click();
        }
    });

    medBtn.addEventListener("click", () => {
        medModal.classList.add("show");
    });

    closeMedBtn.addEventListener("click", () => {
        medModal.classList.remove("show");
    });

    medYesBtn.addEventListener("click", () => {
        alert("Đã ghi nhận: Bệnh nhân ĐÃ uống thuốc");
        medModal.classList.remove("show");
    });

    medNoBtn.addEventListener("click", () => {
        alert("Cảnh báo: Bệnh nhân CHƯA uống thuốc");
        medModal.classList.remove("show");
    });

    async function startListeningState() {
        stopCurrentAudio();
        isListening = true;
        voiceContainer.classList.add("listening");
        voiceStatus.textContent = "Đang lắng nghe bạn...";
        transcriptText.textContent = "...";

        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (Recognition) {
            startBrowserSpeechRecognition(Recognition);
            return;
        }

        await startFirefoxRecording();
    }

    function startBrowserSpeechRecognition(Recognition) {
        const recognition = new Recognition();
        activeRecognition = recognition;
        recognition.lang = "vi-VN";
        recognition.start();

        recognition.onresult = function(event) {
            const userSpeech = event.results[0][0].transcript;
            transcriptText.textContent = `Bạn: "${userSpeech}"`;

            stopListeningState(false);
            voiceStatus.textContent = "Đang suy nghĩ...";
            sendToPython(userSpeech);
        };

        recognition.onerror = function(event) {
            console.error("Lỗi voice:", event.error);
            stopListeningState();
            voiceStatus.textContent = "Không nghe rõ. Nhấn micro thử lại.";
        };

        recognition.onend = function() {
            activeRecognition = null;
            if (isListening) stopListeningState();
        };
    }

    async function startFirefoxRecording() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!navigator.mediaDevices || !AudioContext) {
            stopListeningState(false);
            alert("Firefox không mở được micro. Hãy kiểm tra quyền microphone của trình duyệt.");
            return;
        }

        try {
            recordedChunks = [];
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new AudioContext();
            recordingSampleRate = audioContext.sampleRate;
            audioSource = audioContext.createMediaStreamSource(mediaStream);
            audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);

            audioProcessor.onaudioprocess = (event) => {
                if (!isListening) return;
                const channelData = event.inputBuffer.getChannelData(0);
                recordedChunks.push(new Float32Array(channelData));
            };

            audioSource.connect(audioProcessor);
            audioProcessor.connect(audioContext.destination);
            voiceStatus.textContent = "Đang ghi âm. Bấm micro lần nữa để gửi.";
        } catch (error) {
            console.error("Lỗi mở micro:", error);
            stopListeningState(false);
            alert("Không mở được micro. Hãy cấp quyền microphone cho Firefox.");
        }
    }

    function stopListeningState(sendAudio = true) {
        isListening = false;
        voiceContainer.classList.remove("listening");

        if (activeRecognition) {
            activeRecognition.stop();
            activeRecognition = null;
        }

        if (audioContext) {
            const chunks = recordedChunks;
            const sampleRate = recordingSampleRate;
            stopAudioRecording();

            if (sendAudio) {
                sendRecordedAudio(chunks, sampleRate);
            } else {
                recordedChunks = [];
            }
        } else if (!sendAudio) {
            stopAudioRecording();
        }

        if (voiceStatus.textContent === "Đang lắng nghe bạn...") {
            voiceStatus.textContent = "Đang xử lý...";
        }
    }

    function stopAudioRecording() {
        if (audioProcessor) {
            audioProcessor.disconnect();
            audioProcessor.onaudioprocess = null;
            audioProcessor = null;
        }
        if (audioSource) {
            audioSource.disconnect();
            audioSource = null;
        }
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }
        if (!mediaStream) return;
        mediaStream.getTracks().forEach((track) => track.stop());
        mediaStream = null;
    }

    async function sendRecordedAudio(chunks, sampleRate) {
        if (!chunks.length) {
            voiceStatus.textContent = "Không ghi được âm thanh. Nhấn micro thử lại.";
            return;
        }

        voiceStatus.textContent = "Đang nhận diện giọng nói...";
        const audioBlob = encodeWav(chunks, sampleRate);
        recordedChunks = [];

        try {
            const userSpeech = await transcribeAudio(audioBlob);
            if (!userSpeech) {
                voiceStatus.textContent = "Không nghe rõ. Nhấn micro thử lại.";
                transcriptText.textContent = "Tôi không nghe rõ.";
                return;
            }

            transcriptText.textContent = `Bạn: "${userSpeech}"`;
            voiceStatus.textContent = "Đang suy nghĩ...";
            sendToPython(userSpeech);
        } catch (error) {
            console.error("Lỗi STT:", error);
            voiceStatus.textContent = "Lỗi nhận diện giọng nói. Kiểm tra AI server.";
        }
    }

    function encodeWav(chunks, sampleRate) {
        const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
        const buffer = new ArrayBuffer(44 + totalLength * 2);
        const view = new DataView(buffer);

        writeString(view, 0, "RIFF");
        view.setUint32(4, 36 + totalLength * 2, true);
        writeString(view, 8, "WAVE");
        writeString(view, 12, "fmt ");
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeString(view, 36, "data");
        view.setUint32(40, totalLength * 2, true);

        let offset = 44;
        chunks.forEach((chunk) => {
            for (let i = 0; i < chunk.length; i++) {
                const sample = Math.max(-1, Math.min(1, chunk[i]));
                view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
                offset += 2;
            }
        });

        return new Blob([view], { type: "audio/wav" });
    }

    function writeString(view, offset, text) {
        for (let i = 0; i < text.length; i++) {
            view.setUint8(offset + i, text.charCodeAt(i));
        }
    }

    async function transcribeAudio(audioBlob) {
        const formData = new FormData();
        formData.append("audio", audioBlob, "speech.wav");

        const response = await fetch("http://127.0.0.1:5001/stt", {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error(`STT failed with status ${response.status}`);
        }

        const data = await response.json();
        return (data.text || "").trim();
    }

    async function sendToPython(text) {
        try {
            const response = await fetch("http://127.0.0.1:5001/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();
            const aiReply = data.reply;
            transcriptText.textContent = `AI: "${aiReply}"`;
            await speakFromServer(aiReply);
        } catch (error) {
            console.error("Lỗi kết nối Python:", error);
            transcriptText.textContent = "Lỗi: Chưa bật AI server!";
        }
    }

    function stopCurrentAudio() {
        if (!currentAudio) return;
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
    }

    async function speakFromServer(text) {
        stopCurrentAudio();
        voiceStatus.textContent = "Đang phát giọng nói...";

        const smallRobot = document.querySelector(".small-robot");
        if (smallRobot) smallRobot.classList.add("talking");

        try {
            const response = await fetch("http://127.0.0.1:5001/tts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });

            if (!response.ok) {
                throw new Error(`TTS failed with status ${response.status}`);
            }

            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            currentAudio = new Audio(audioUrl);

            currentAudio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                if (smallRobot) smallRobot.classList.remove("talking");
                voiceStatus.textContent = "Nhấn micro để nói tiếp.";
                currentAudio = null;
            };

            currentAudio.onerror = (e) => {
                console.error("Lỗi phát audio TTS:", e);
                URL.revokeObjectURL(audioUrl);
                if (smallRobot) smallRobot.classList.remove("talking");
                voiceStatus.textContent = "Lỗi TTS. Nhấn micro để thử lại.";
                currentAudio = null;
            };

            await currentAudio.play();
        } catch (error) {
            console.error("Lỗi gọi TTS server:", error);
            if (smallRobot) smallRobot.classList.remove("talking");
            voiceStatus.textContent = "Lỗi TTS server. Kiểm tra Python server.";
        }
    }
});
