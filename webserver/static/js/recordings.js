// In your recordings.js file
function loadRecordings() {
  console.log("Starting to load recordings...");

  // Add a timestamp parameter to prevent caching
  fetch("/api/recordings?t=" + new Date().getTime())
    .then((response) => {
      console.log("API response status:", response.status);
      if (!response.ok) {
        throw new Error(`API returned status ${response.status}`);
      }
      return response.json();
    })
    .then((files) => {
      console.log("Files returned by API:", files);

      const recordingList = document.getElementById("recording-list");
      if (!recordingList) {
        console.error("recording-list element not found in DOM");
        return;
      }

      recordingList.innerHTML = "";

      if (!files || files.length === 0) {
        console.log("No files returned by API");
        // Display empty state message
        const emptyRow = document.createElement("tr");
        emptyRow.innerHTML = `
          <td colspan="5" class="py-8 text-center">
            <div class="flex flex-col items-center">
              <i class="fas fa-microphone-slash text-4xl text-gray-300 dark:text-gray-600 mb-3"></i>
              <p class="text-gray-500 dark:text-gray-400">No recordings yet.</p>
              <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Recordings will appear here when created.</p>
            </div>
          </td>
        `;
        recordingList.appendChild(emptyRow);

        // Hide the action buttons when there are no recordings
        document.getElementById('download-selected')?.classList.add("hidden");
        document.getElementById('delete-selected')?.classList.add("hidden");
      } else {
        // Show the action buttons when there are recordings
        document.getElementById('download-selected')?.classList.remove("hidden");
        document.getElementById('delete-selected')?.classList.remove("hidden");

        // Add recording items
        files.forEach((filename, index) => {
          console.log(`Creating item ${index + 1}/${files.length}: ${filename}`);
          try {
            const item = createRecordingItem(filename);
            recordingList.appendChild(item);
          } catch (err) {
            console.error(`Error creating item for ${filename}:`, err);
          }
        });
      }

      try {
        console.log("Setting up event listeners");
        setupEventListeners();
      } catch (err) {
        console.error("Error in setupEventListeners:", err);
      }

      try {
        // Initialize Plyr only on desktop/tablet (md and up)
        const isDesktop = window.matchMedia && window.matchMedia('(min-width: 768px)').matches;
        console.log("Initializing audio players (desktop only):", isDesktop);
        const audioElements = document.querySelectorAll('audio');
        console.log(`Found ${audioElements.length} audio elements`);

        let players = [];
        if (isDesktop) {
          players = Array.from(audioElements).map(p => {
            // Ensure audio elements are set up for proper loading
            p.preload = "metadata";

            // Desktop: full controls with progress
            return new Plyr(p, {
              controls: ['play', 'progress', 'current-time', 'duration', 'mute', 'volume'],
              displayDuration: true,
              hideControls: false,
              invertTime: false,
              toggleInvert: false,
              seekTime: 5,
              tooltips: { controls: false, seek: false },
              fullscreen: { enabled: false },
              keyboard: { focused: true, global: false }
            });
          });
        } else {
          // Mobile: keep native <audio> hidden and control via compact button
          Array.from(audioElements).forEach(p => { p.preload = 'metadata'; });
        }

        improveAudioDurationDetection();
        console.log(`Initialized ${players.length} Plyr players`);
      } catch (err) {
        console.error("Error initializing audio players:", err);
      }
      
      // Check for processing recordings and start polling if needed
      checkForProcessingRecordings();
    })
    .catch((error) => {
      console.error("Error loading recordings:", error);

      // Show error in UI if toast function exists
      if (typeof showToast === 'function') {
        showToast("Failed to load recordings: " + error.message, "error");
      } else {
        console.error("showToast function not available");

        // Fallback error display if toast isn't available
        const recordingList = document.getElementById("recording-list");
        if (recordingList) {
          recordingList.innerHTML = `
            <tr>
              <td colspan="5" class="p-4 text-center text-red-600">
                <div class="flex flex-col items-center">
                  <i class="fas fa-exclamation-circle text-4xl mb-3"></i>
                  <p class="font-semibold">Error loading recordings</p>
                  <p class="text-sm mt-1">${error.message}</p>
                  <button onclick="loadRecordings()" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
                    Retry
                  </button>
                </div>
              </td>
            </tr>
          `;
        }
      }
    });
}

function improveAudioDurationDetection() {
  document.querySelectorAll('audio').forEach(audio => {
    // For WAV files specifically
    if (audio.src.toLowerCase().endsWith('.wav')) {
      // Try to force metadata loading
      audio.addEventListener('loadedmetadata', () => {
        // If duration is infinity or unusually small, try to fix it
        if (!isFinite(audio.duration) || audio.duration < 0.1) {
          console.log('Attempting to fix infinite duration for WAV file...');

          // Force a tiny play/pause to get Chrome to recalculate
          const playPromise = audio.play();
          if (playPromise !== undefined) {
            playPromise.then(() => {
              setTimeout(() => {
                audio.pause();
                console.log(`New duration after fix: ${audio.duration}`);
              }, 10);
            }).catch(err => {
              console.warn('Play attempt to fix duration failed:', err);
            });
          }
        }
      });

      // Add error handling
      audio.addEventListener('error', (e) => {
        console.error('Audio error:', e);
      });
    }
  });
}

function createRecordingItem(recording) {
  // Handle both old format (string) and new format (object)
  const filename = typeof recording === 'string' ? recording : recording.filename;
  const metadata = typeof recording === 'object' ? recording : {};
  
  const row = document.createElement("tr");
  row.className =
    "recording-item border-b border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors duration-200";

  const dateTime = parseDateTime(filename);
  const formattedDate = moment(dateTime).format("MMMM D, YYYY [at] h:mm A");

  // Generate a random pastel color for the recording icon
  const hue = Math.floor(Math.random() * 360);
  const iconColor = `hsl(${hue}, 70%, 80%)`;
  
  // Use AI-generated title or filename
  const displayTitle = metadata.title || filename;
  const isProcessed = metadata.processing_status === 'completed';
  const isProcessing = metadata.processing_status === 'processing';
  const isPending = metadata.processing_status === 'pending';
  
  // Processing status indicator (no checkmark for completed)
  let statusIndicator = '';
  if (isProcessing) {
    statusIndicator = '<i class="fas fa-spinner fa-spin ml-2 text-blue-500" title="Processing..."></i>';
  } else if (isPending) {
    statusIndicator = '<i class="fas fa-clock ml-2 text-gray-400" title="Pending processing"></i>';
  }
  
  // Format speaker names with commas
  const speakerDisplay = metadata.speaker_names && metadata.speaker_names.length > 0
    ? `<span class="text-xs text-gray-600 dark:text-gray-400">${metadata.speaker_names.join(', ')}</span>`
    : '';
  
  // Category badge with Tailwind pill style with border and dot
  const categoryConfig = {
    joyful:    { bg: 'bg-yellow-50 dark:bg-yellow-950', text: 'text-yellow-700 dark:text-yellow-300', border: 'border-yellow-600/10 dark:border-yellow-400/20', dot: 'fill-yellow-500 dark:fill-yellow-400' },
    heartfelt: { bg: 'bg-red-50 dark:bg-red-950', text: 'text-red-700 dark:text-red-300', border: 'border-red-600/10 dark:border-red-400/20', dot: 'fill-red-500 dark:fill-red-400' },
    humorous:  { bg: 'bg-green-50 dark:bg-green-950', text: 'text-green-700 dark:text-green-300', border: 'border-green-600/10 dark:border-green-400/20', dot: 'fill-green-500 dark:fill-green-400' },
    nostalgic: { bg: 'bg-purple-50 dark:bg-purple-950', text: 'text-purple-700 dark:text-purple-300', border: 'border-purple-600/10 dark:border-purple-400/20', dot: 'fill-purple-500 dark:fill-purple-400' },
    advice:    { bg: 'bg-blue-50 dark:bg-blue-950', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-600/10 dark:border-blue-400/20', dot: 'fill-blue-500 dark:fill-blue-400' },
    blessing:  { bg: 'bg-indigo-50 dark:bg-indigo-950', text: 'text-indigo-700 dark:text-indigo-300', border: 'border-indigo-600/10 dark:border-indigo-400/20', dot: 'fill-indigo-500 dark:fill-indigo-400' },
    toast:     { bg: 'bg-pink-50 dark:bg-pink-950', text: 'text-pink-700 dark:text-pink-300', border: 'border-pink-600/10 dark:border-pink-400/20', dot: 'fill-pink-500 dark:fill-pink-400' },
    gratitude: { bg: 'bg-teal-50 dark:bg-teal-950', text: 'text-teal-700 dark:text-teal-300', border: 'border-teal-600/10 dark:border-teal-400/20', dot: 'fill-teal-500 dark:fill-teal-400' },
    apology:   { bg: 'bg-gray-50 dark:bg-gray-950', text: 'text-gray-700 dark:text-gray-300', border: 'border-gray-600/10 dark:border-gray-400/20', dot: 'fill-gray-500 dark:fill-gray-400' },
    other:     { bg: 'bg-gray-50 dark:bg-gray-950', text: 'text-gray-700 dark:text-gray-300', border: 'border-gray-600/10 dark:border-gray-400/20', dot: 'fill-gray-500 dark:fill-gray-400' }
  };
  
  // Function to generate consistent color for unknown categories
  const getCategoryStyle = (categoryName) => {
    if (categoryConfig[categoryName]) {
      return categoryConfig[categoryName];
    }
    // Generate consistent color from category name hash
    const colors = [
      { bg: 'bg-amber-50 dark:bg-amber-950', text: 'text-amber-700 dark:text-amber-300', border: 'border-amber-600/10 dark:border-amber-400/20', dot: 'fill-amber-500 dark:fill-amber-400' },
      { bg: 'bg-lime-50 dark:bg-lime-950', text: 'text-lime-700 dark:text-lime-300', border: 'border-lime-600/10 dark:border-lime-400/20', dot: 'fill-lime-500 dark:fill-lime-400' },
      { bg: 'bg-cyan-50 dark:bg-cyan-950', text: 'text-cyan-700 dark:text-cyan-300', border: 'border-cyan-600/10 dark:border-cyan-400/20', dot: 'fill-cyan-500 dark:fill-cyan-400' },
      { bg: 'bg-fuchsia-50 dark:bg-fuchsia-950', text: 'text-fuchsia-700 dark:text-fuchsia-300', border: 'border-fuchsia-600/10 dark:border-fuchsia-400/20', dot: 'fill-fuchsia-500 dark:fill-fuchsia-400' },
      { bg: 'bg-rose-50 dark:bg-rose-950', text: 'text-rose-700 dark:text-rose-300', border: 'border-rose-600/10 dark:border-rose-400/20', dot: 'fill-rose-500 dark:fill-rose-400' },
      { bg: 'bg-violet-50 dark:bg-violet-950', text: 'text-violet-700 dark:text-violet-300', border: 'border-violet-600/10 dark:border-violet-400/20', dot: 'fill-violet-500 dark:fill-violet-400' },
      { bg: 'bg-sky-50 dark:bg-sky-950', text: 'text-sky-700 dark:text-sky-300', border: 'border-sky-600/10 dark:border-sky-400/20', dot: 'fill-sky-500 dark:fill-sky-400' },
      { bg: 'bg-emerald-50 dark:bg-emerald-950', text: 'text-emerald-700 dark:text-emerald-300', border: 'border-emerald-600/10 dark:border-emerald-400/20', dot: 'fill-emerald-500 dark:fill-emerald-400' }
    ];
    const hash = categoryName.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length];
  };
  
  const category = getCategoryStyle(metadata.category);
  const categoryBadge = metadata.category
    ? `<span class="inline-flex items-center gap-x-1.5 rounded-full px-2 py-1 text-xs font-medium border ${category.bg} ${category.text} ${category.border}">
         <svg class="h-1.5 w-1.5 ${category.dot}" viewBox="0 0 6 6" aria-hidden="true">
           <circle cx="3" cy="3" r="3" />
         </svg>
         ${metadata.category}
       </span>`
    : '';

  const mobileControls = `
      <div class=\"sm:hidden mt-2 flex items-center gap-3\">
        <button class=\"mobile-play bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm\" title=\"Play/Pause\">
          <i class=\"fas fa-play text-sm\"></i>
        </button>
        <span class=\"mobile-duration text-xs text-gray-600 dark:text-gray-400\"></span>
      </div>`;

  const mobileDate = `<p class=\"sm:hidden mt-1 text-xs text-gray-500 dark:text-gray-400\">${formattedDate}</p>`;

  row.innerHTML = `
      <td class="p-2 text-center"><input type="checkbox" class="recording-checkbox w-4 h-4" data-id="${filename}"></td>
      <td class="p-2">
        <div class="flex items-center">
          <div class="w-8 h-8 rounded-full flex items-center justify-center mr-3 flex-shrink-0" style="background-color: ${iconColor}">
            <i class="fas fa-microphone text-white"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="recording-name font-semibold cursor-pointer hover:text-blue-600 truncate"
                    data-filename="${filename}"
                    title="${metadata.transcription ? 'Click to view transcription' : filename}">
                ${displayTitle}
              </span>
              ${statusIndicator}
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              ${speakerDisplay ? `<div class=\"flex items-center gap-1\">${speakerDisplay}</div>` : ''}
              ${categoryBadge}
            </div>
            ${mobileDate}
            ${mobileControls}
          </div>
        </div>
      </td>
      <td class="p-2 hidden md:table-cell">
        <audio class="audio-player" src="/recordings/${filename}"></audio>
      </td>
      <td class="p-2 recording-date text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap hidden sm:table-cell">${formattedDate}</td>
      <td class="p-2 text-right">
        <div class="flex items-center justify-end gap-2">
          ${metadata.transcription ? `<button class="view-transcript-button bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm" title="View transcription">
            <i class="fas fa-file-alt text-sm"></i>
          </button>` : ''}
          <button class="delete-button bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700 text-white rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm" title="Delete">
            <i class="fas fa-times text-sm"></i>
          </button>
        </div>
      </td>
    `;
  
  // Add click handlers
  const nameSpan = row.querySelector('.recording-name');
  nameSpan.addEventListener('click', (e) => {
    e.stopPropagation();
    if (metadata.transcription) {
      showTranscriptionModal(filename, metadata);
    }
  });
  
  // Mobile play/pause control
  const audioEl = row.querySelector('audio');
  const mobilePlayBtn = row.querySelector('.mobile-play');
  const mobileDuration = row.querySelector('.mobile-duration');

  if (audioEl) {
    // Update duration label when known
    const updateDuration = () => {
      if (isFinite(audioEl.duration) && audioEl.duration > 0) {
        const mins = Math.floor(audioEl.duration / 60);
        const secs = Math.floor(audioEl.duration % 60).toString().padStart(2, '0');
        mobileDuration && (mobileDuration.textContent = `${mins}:${secs}`);
      }
    };
    audioEl.addEventListener('loadedmetadata', updateDuration);
    // Fallback attempt like desktop helper
    if (!isFinite(audioEl.duration) || audioEl.duration < 0.1) {
      const playPromise = audioEl.play();
      if (playPromise !== undefined) {
        playPromise.then(() => setTimeout(() => audioEl.pause(), 10)).catch(() => {});
      }
    }
  }

  if (mobilePlayBtn && audioEl) {
    mobilePlayBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Pause any other playing audio
      document.querySelectorAll('audio').forEach(a => {
        if (a !== audioEl && !a.paused) a.pause();
      });
      if (audioEl.paused) {
        audioEl.play();
        mobilePlayBtn.innerHTML = '<i class="fas fa-pause text-sm"></i>';
      } else {
        audioEl.pause();
        mobilePlayBtn.innerHTML = '<i class="fas fa-play text-sm"></i>';
      }
    });
    // Sync button when playback ends
    audioEl && audioEl.addEventListener('ended', () => {
      mobilePlayBtn.innerHTML = '<i class="fas fa-play text-sm"></i>';
    });
  }
  
  // Add handler for view transcript button
  const transcriptButton = row.querySelector('.view-transcript-button');
  if (transcriptButton) {
    transcriptButton.addEventListener('click', (e) => {
      e.stopPropagation();
      showTranscriptionModal(filename, metadata);
    });
  }

  row.dataset.filename = filename;
  row.dataset.status = metadata.processing_status || '';
  return row;
}

function parseDateTime(filename) {
  const regex = /(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/;
  const match = filename.match(regex);
  return match ? match[1] : null;
}

function setupEventListeners() {
  const selectAllCheckbox = document.getElementById("select-all");
  const downloadSelectedButton = document.getElementById("download-selected");
  const deleteSelectedButton = document.getElementById("delete-selected");
  const recordingItems = document.querySelectorAll(".recording-item");

  selectAllCheckbox.addEventListener("change", function () {
    const isChecked = this.checked;
    recordingItems.forEach((item) => {
      item.querySelector(".recording-checkbox").checked = isChecked;
      item.classList.toggle("selected", isChecked);
    });
  });

  downloadSelectedButton.addEventListener("click", function () {
    const selectedFiles = Array.from(
      document.querySelectorAll(".recording-checkbox:checked"),
    ).map((checkbox) => checkbox.closest(".recording-item").dataset.filename);

    if (selectedFiles.length === 0) {
      alert("Please select at least one recording to download.");
      return;
    }

    // Create a form to submit the selected files
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/download-selected";

    selectedFiles.forEach((filename) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "files[]";
      input.value = filename;
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  });

  deleteSelectedButton.addEventListener("click", function() {
    const selectedItems = document.querySelectorAll('.recording-checkbox:checked');
    if (selectedItems.length === 0) {
      alert('Please select at least one recording to delete.');
      return;
    }

    if (confirm(`Are you sure you want to delete ${selectedItems.length} selected recording(s)?`)) {
      const idsToDelete = Array.from(selectedItems).map(checkbox => checkbox.dataset.id);

      fetch('/delete-recordings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ids: idsToDelete })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Remove deleted items from the DOM
          selectedItems.forEach(checkbox => {
            checkbox.closest('tr').remove();
          });

          // Show success message
          if (typeof showToast === 'function') {
            showToast(`Deleted ${selectedItems.length} recording(s)`, 'success');
          }

          // Check if all recordings were deleted
          if (document.querySelectorAll('.recording-item').length === 0) {
            loadRecordings(); // Reload to show empty state
          }
        } else {
          throw new Error(data.message || 'Failed to delete recordings');
        }
      })
      .catch(error => {
        console.error('Error:', error);
        if (typeof showToast === 'function') {
          showToast('Error deleting recordings: ' + error.message, 'error');
        } else {
          alert('Error deleting recordings: ' + error.message);
        }
      });
    }
  });

  recordingItems.forEach((item) => {
    item.addEventListener("click", function (e) {
      if (e.target.type === "checkbox") return; // Don't toggle selection when clicking the checkbox
      if (e.target.closest('.plyr')) return; // Don't toggle selection when clicking the player
      if (e.target.closest('.mobile-play')) return; // Don't toggle when clicking mobile play
      if (e.target.closest('.delete-button')) return; // Don't toggle selection when clicking delete
      if (e.target.closest('.view-transcript-button')) return; // Don't toggle when clicking transcript button
      if (e.target.classList.contains('recording-name')) return; // Don't toggle when clicking the name

      const checkbox = this.querySelector(".recording-checkbox");
      checkbox.checked = !checkbox.checked;
      this.classList.toggle("selected", checkbox.checked);
      updateSelectAllCheckbox();
    });

    const checkbox = item.querySelector(".recording-checkbox");
    checkbox.addEventListener("change", function () {
      item.classList.toggle("selected", this.checked);
      updateSelectAllCheckbox();
    });
  });

  // Detect mobile devices to activate swipe only on mobile
  if (isMobileDevice()) {
    recordingItems.forEach((item) => {
      const hammer = new Hammer(item);
      hammer.on("swipeleft", function () {
        // Animate swipe left
        item.style.transition = "transform 0.3s ease-out";
        item.style.transform = "translateX(-100%)";
        setTimeout(() => {
          if (
            confirm(`Are you sure you want to delete ${item.dataset.filename}?`)
          ) {
            fetch(`/delete/${item.dataset.filename}`, { method: "POST" }).then(
              () => loadRecordings(),
            );
          } else {
            // Reset position if canceled
            item.style.transform = "translateX(0)";
          }
        }, 300); // Wait for animation to finish
      });
    });
  }

  // Handle click-to-delete for desktop users
  document.querySelectorAll(".delete-button").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.stopPropagation(); // Prevent row click event
      const item = button.closest(".recording-item");
      if (
        confirm(`Are you sure you want to delete ${item.dataset.filename}?`)
      ) {
        fetch(`/delete/${item.dataset.filename}`, { method: "POST" }).then(() =>
          loadRecordings(),
        );
      }
    });
  });

  // Handle renaming the recording when the title is edited
  document.querySelectorAll(".recording-name").forEach((span) => {
    span.addEventListener("blur", function () {
      const newFilename = span.innerText.trim();
      const oldFilename = span.closest(".recording-item").dataset.filename;
      if (newFilename !== oldFilename) {
        // Send a request to rename the file
        fetch(`/rename/${oldFilename}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ newFilename }),
        })
          .then(() => {
            loadRecordings();
          })
          .catch((err) => {
            console.error("Rename error:", err);
            alert("Failed to rename the file.");
          });
      }
    });
  });
}

function updateSelectAllCheckbox() {
  const selectAllCheckbox = document.getElementById("select-all");
  const allCheckboxes = document.querySelectorAll(".recording-checkbox");
  const allChecked = Array.from(allCheckboxes).every(
    (checkbox) => checkbox.checked,
  );
  selectAllCheckbox.checked = allChecked;
}

function isMobileDevice() {
  return /Mobi|Android/i.test(navigator.userAgent);
}

function showTranscriptionModal(filename, recording) {
  if (!recording.transcription) {
    alert('Transcription not available for this recording.');
    return;
  }
  
  // Create modal overlay
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
  modal.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-2xl p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Transcription</h2>
        <button class="close-modal text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
          <i class="fas fa-times text-2xl"></i>
        </button>
      </div>
      
      <div class="mb-4 space-y-2 border-b border-gray-200 dark:border-gray-600 pb-4">
        <p class="text-sm text-gray-700 dark:text-gray-300">
          <strong class="text-gray-900 dark:text-white">File:</strong> ${filename}
        </p>
        ${recording.speaker_names && recording.speaker_names.length > 0 ? `
          <p class="text-sm text-gray-700 dark:text-gray-300">
            <strong class="text-gray-900 dark:text-white">Speakers:</strong> ${recording.speaker_names.join(', ')}
          </p>
        ` : ''}
        ${recording.category ? `
          <p class="text-sm text-gray-700 dark:text-gray-300">
            <strong class="text-gray-900 dark:text-white">Category:</strong> ${recording.category}
          </p>
        ` : ''}
        ${recording.confidence ? `
          <p class="text-sm text-gray-700 dark:text-gray-300">
            <strong class="text-gray-900 dark:text-white">Confidence:</strong> ${(recording.confidence * 100).toFixed(0)}%
          </p>
        ` : ''}
      </div>
      
      <div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
        <p class="text-base text-gray-900 dark:text-gray-100 whitespace-pre-wrap leading-relaxed">
          ${recording.transcription}
        </p>
      </div>
    </div>
  `;
  
  // Close on background click or X button
  modal.addEventListener('click', (e) => {
    if (e.target === modal || e.target.closest('.close-modal')) {
      document.body.removeChild(modal);
    }
  });
  
  document.body.appendChild(modal);
}

// Poll for updates when recordings are processing
let refreshInterval = null;

function checkForProcessingRecordings() {
  const processingItems = document.querySelectorAll('[data-status="processing"],[data-status="pending"]');
  
  if (processingItems.length > 0 && !refreshInterval) {
    // Start polling every 10 seconds
    refreshInterval = setInterval(() => {
      console.log('Refreshing recordings (processing in progress)...');
      loadRecordings();
    }, 10000);
  } else if (processingItems.length === 0 && refreshInterval) {
    // Stop polling when nothing is processing
    clearInterval(refreshInterval);
    refreshInterval = null;
    console.log('All recordings processed, stopped polling');
  }
}

// Initialize recordings on page load
document.addEventListener("DOMContentLoaded", function () {
  loadRecordings();
});
