// Global variable to store all recordings for filtering
let allRecordings = [];
let searchDebounceTimer = null;

// Format time without leading zeros (e.g., 0:55 instead of 00:55, 10:12 stays as 10:12)
function formatTime(seconds) {
  if (!isFinite(seconds) || seconds < 0) return '0:00';
  
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
}

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

      // Store recordings globally for filtering
      allRecordings = files;
      
      // Populate speaker filter dropdown
      populateSpeakerFilter();
      
      // Apply current filters (if any)
      applyFilters();
      
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
    // Just add error handling, no autoplay workaround
    audio.addEventListener('error', (e) => {
      console.error('Audio error:', e);
    });
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

  // Generate a random color for the recording icon - label maker style
  const colors = [
    { bg: '#FCD34D', border: '#000', text: '#000' }, // Yellow
    { bg: '#FDE047', border: '#000', text: '#000' }, // Light yellow
    { bg: '#FEF08A', border: '#000', text: '#000' }, // Pale yellow
    { bg: '#FEF3C7', border: '#000', text: '#000' }, // Very pale yellow
    { bg: '#FFF4E6', border: '#000', text: '#000' }, // Cream
    { bg: '#FFFBEB', border: '#000', text: '#000' }, // Light cream
  ];
  const randomColor = colors[Math.floor(Math.random() * colors.length)];
  
  // Use AI-generated title or filename
  const displayTitle = metadata.title || filename;
  const isProcessed = metadata.processing_status === 'completed';
  const isProcessing = metadata.processing_status === 'processing';
  const isPending = metadata.processing_status === 'pending';
  
  // Processing status indicator (no checkmark for completed)
  let statusIndicator = '';
  if (isProcessing) {
    statusIndicator = '<i class="fas fa-spinner fa-spin ml-2 text-blue-500 self-center align-middle" title="Processing..."></i>';
  } else if (isPending) {
    statusIndicator = '<i class="fas fa-clock ml-2 text-gray-400 self-center align-middle" title="Pending processing"></i>';
  }
  
  // Format speaker names as pills with person icons
  const speakerDisplay = metadata.speaker_names && metadata.speaker_names.length > 0
    ? metadata.speaker_names.map(name => 
        `<span class="inline-flex items-center gap-x-1.5 rounded-full px-2 py-1 text-xs font-medium border bg-gray-50 dark:bg-gray-900 text-gray-700 dark:text-gray-300 border-gray-600/10 dark:border-gray-400/20">
           <svg class="h-3 w-3 fill-gray-500 dark:fill-gray-400 flex-shrink-0" viewBox="0 0 20 20" aria-hidden="true">
             <path d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" />
           </svg>
           ${name}
         </span>`
      ).join(' ')
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
    // Handle null/undefined categories
    if (!categoryName) {
      return categoryConfig['other'];
    }
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
      <div class=\"md:hidden mt-2 flex items-center justify-between gap-2\">
        <div class=\"flex items-center gap-2 flex-shrink-0\">
          <button class=\"mobile-play bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm\" title=\"Play/Pause\">
            <i class=\"fas fa-play text-sm\"></i>
          </button>
          <span class=\"mobile-duration text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap\"></span>
        </div>
        <div class=\"flex items-center gap-2 flex-shrink-0 sm:hidden\">
          ${metadata.transcription ? `<button class=\"mobile-transcript-button bg-blue-500 hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700 text-white rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm\" title=\"View transcription\">
            <i class=\"fas fa-file-alt text-sm\"></i>
          </button>` : ''}
          <button class=\"mobile-delete-button bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700 text-white rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm\" title=\"Delete\">
            <i class=\"fas fa-times text-sm\"></i>
          </button>
        </div>
      </div>`;

  const mobileDate = `<p class=\"md:hidden mt-1 text-xs text-gray-500 dark:text-gray-400\">${formattedDate}</p>`;

  row.innerHTML = `
      <td class="p-2 text-center w-10"><input type="checkbox" class="recording-checkbox w-4 h-4" data-id="${filename}"></td>
      <td class="p-2">
        <div class="flex items-start">
          <div class="hidden xl:flex w-10 h-10 items-center justify-center mr-3 flex-shrink-0 border-2" style="background-color: ${randomColor.bg}; border-color: ${randomColor.border};">
            <i class="fas fa-microphone text-sm" style="color: ${randomColor.text};"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class=\"flex items-center gap-1 mb-1 min-w-0\">
              <span class="recording-name font-semibold cursor-pointer hover:text-blue-600 block flex-1 min-w-0 break-words"
                    data-filename="${filename}"
                    title="${metadata.transcription ? 'Click to view transcription' : filename}">
                ${displayTitle}
              </span>
              ${statusIndicator}
            </div>
            <div class="flex items-center gap-1 flex-wrap min-w-0">
              ${speakerDisplay}
              ${categoryBadge}
            </div>
            ${mobileDate}
            ${mobileControls}
          </div>
        </div>
      </td>
      <td class="p-2 hidden md:table-cell">
        <audio class="audio-player" src="/recordings/${filename}"></audio>
        <div class="tablet-compact-player flex items-center gap-2">
          <button class="tablet-play bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-md w-8 h-8 inline-flex items-center justify-center transition-colors duration-200 shadow-sm" title="Play/Pause">
            <i class="fas fa-play text-sm"></i>
          </button>
          <span class="tablet-duration text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap"></span>
        </div>
      </td>
      <td class="p-2 recording-date text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap hidden sm:table-cell">${formattedDate}</td>
      <td class="p-2 text-right hidden sm:table-cell">
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
    // Also update during playback for current time
    audioEl.addEventListener('timeupdate', () => {
      if (isFinite(audioEl.currentTime) && isFinite(audioEl.duration) && audioEl.duration > 0) {
        const currentMins = Math.floor(audioEl.currentTime / 60);
        const currentSecs = Math.floor(audioEl.currentTime % 60).toString().padStart(2, '0');
        const totalMins = Math.floor(audioEl.duration / 60);
        const totalSecs = Math.floor(audioEl.duration % 60).toString().padStart(2, '0');
        mobileDuration && (mobileDuration.textContent = `${currentMins}:${currentSecs} / ${totalMins}:${totalSecs}`);
      }
    });
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
  
  // Tablet play/pause control (768-1024px)
  const tabletPlayBtn = row.querySelector('.tablet-play');
  const tabletDuration = row.querySelector('.tablet-duration');
  
  if (tabletPlayBtn && audioEl) {
    // Update duration label
    const updateTabletDuration = () => {
      if (isFinite(audioEl.duration) && audioEl.duration > 0) {
        const mins = Math.floor(audioEl.duration / 60);
        const secs = Math.floor(audioEl.duration % 60).toString().padStart(2, '0');
        tabletDuration && (tabletDuration.textContent = `${mins}:${secs}`);
      }
    };
    audioEl.addEventListener('loadedmetadata', updateTabletDuration);
    // Also update during playback
    audioEl.addEventListener('timeupdate', () => {
      if (isFinite(audioEl.currentTime) && isFinite(audioEl.duration) && audioEl.duration > 0) {
        const currentMins = Math.floor(audioEl.currentTime / 60);
        const currentSecs = Math.floor(audioEl.currentTime % 60).toString().padStart(2, '0');
        const totalMins = Math.floor(audioEl.duration / 60);
        const totalSecs = Math.floor(audioEl.duration % 60).toString().padStart(2, '0');
        tabletDuration && (tabletDuration.textContent = `${currentMins}:${currentSecs} / ${totalMins}:${totalSecs}`);
      }
    });
    
    tabletPlayBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Pause any other playing audio
      document.querySelectorAll('audio').forEach(a => {
        if (a !== audioEl && !a.paused) a.pause();
      });
      if (audioEl.paused) {
        audioEl.play();
        tabletPlayBtn.innerHTML = '<i class="fas fa-pause text-sm"></i>';
      } else {
        audioEl.pause();
        tabletPlayBtn.innerHTML = '<i class="fas fa-play text-sm"></i>';
      }
    });
    // Sync button when playback ends
    audioEl.addEventListener('ended', () => {
      tabletPlayBtn.innerHTML = '<i class="fas fa-play text-sm"></i>';
    });
  }
  
  // Add handler for desktop view transcript button
  const transcriptButton = row.querySelector('.view-transcript-button');
  if (transcriptButton) {
    transcriptButton.addEventListener('click', (e) => {
      e.stopPropagation();
      showTranscriptionModal(filename, metadata);
    });
  }
  
  // Add handler for mobile view transcript button
  const mobileTranscriptButton = row.querySelector('.mobile-transcript-button');
  if (mobileTranscriptButton) {
    mobileTranscriptButton.addEventListener('click', (e) => {
      e.stopPropagation();
      showTranscriptionModal(filename, metadata);
    });
  }
  
  // Add handler for mobile delete button
  const mobileDeleteButton = row.querySelector('.mobile-delete-button');
  if (mobileDeleteButton) {
    mobileDeleteButton.addEventListener('click', (e) => {
      e.stopPropagation();
      const item = mobileDeleteButton.closest('.recording-item');
      if (confirm(`Are you sure you want to delete ${item.dataset.filename}?`)) {
        fetch(`/delete/${item.dataset.filename}`, { method: 'POST' }).then(() => loadRecordings());
      }
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
      if (e.target.closest('.mobile-delete-button')) return; // Don't toggle when clicking mobile delete
      if (e.target.closest('.view-transcript-button')) return; // Don't toggle when clicking transcript button
      if (e.target.closest('.mobile-transcript-button')) return; // Don't toggle when clicking mobile transcript
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
  
  // Trim leading/trailing whitespace from transcription
  const cleanTranscription = recording.transcription.trim();
  
  // Generate speaker badges (reuse logic from main list)
  const speakerBadges = recording.speaker_names && recording.speaker_names.length > 0
    ? recording.speaker_names.map(name => 
        `<span class="inline-flex items-center gap-x-1.5 rounded-full px-2 py-1 text-xs font-medium border bg-gray-50 dark:bg-gray-900 text-gray-700 dark:text-gray-300 border-gray-600/10 dark:border-gray-400/20">
           <svg class="h-3 w-3 fill-gray-500 dark:fill-gray-400 flex-shrink-0" viewBox="0 0 20 20" aria-hidden="true">
             <path d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" />
           </svg>
           ${name}
         </span>`
      ).join(' ')
    : '';
  
  // Generate category badge (reuse category config)
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
  
  const category = categoryConfig[recording.category] || categoryConfig['other'];
  const categoryBadge = recording.category
    ? `<span class="inline-flex items-center gap-x-1.5 rounded-full px-2 py-1 text-xs font-medium border ${category.bg} ${category.text} ${category.border}">
         <svg class="h-1.5 w-1.5 ${category.dot}" viewBox="0 0 6 6" aria-hidden="true">
           <circle cx="3" cy="3" r="3" />
         </svg>
         ${recording.category}
       </span>`
    : '';
  
  // Get title for modal header
  const displayTitle = recording.title || filename;
  
  // Create modal overlay
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
  modal.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-2xl p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
      <div class="flex justify-between items-start mb-4">
        <div class="flex-1 pr-4">
          <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-1">${displayTitle}</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400">${filename}</p>
        </div>
        <button class="close-modal text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 flex-shrink-0">
          <i class="fas fa-times text-2xl"></i>
        </button>
      </div>
      
      <div class="mb-4 space-y-3 border-b border-gray-200 dark:border-gray-600 pb-4">
        ${speakerBadges ? `
          <div>
            <strong class="text-sm text-gray-900 dark:text-white block mb-2">Speakers:</strong>
            <div class="flex flex-wrap gap-1">${speakerBadges}</div>
          </div>
        ` : ''}
        ${categoryBadge ? `
          <div>
            <strong class="text-sm text-gray-900 dark:text-white block mb-2">Category:</strong>
            <div>${categoryBadge}</div>
          </div>
        ` : ''}
        ${recording.confidence ? `
          <p class="text-sm text-gray-700 dark:text-gray-300">
            <strong class="text-gray-900 dark:text-white">Confidence:</strong> ${(recording.confidence * 100).toFixed(0)}%
          </p>
        ` : ''}
      </div>
      
      <div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
        <p class="text-base text-gray-900 dark:text-gray-100 whitespace-pre-wrap leading-relaxed">${cleanTranscription}</p>
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

// Populate speaker filter with unique speakers from all recordings
function populateSpeakerFilter() {
  const speakerSelect = document.getElementById('filter-speaker');
  if (!speakerSelect) return;
  
  // Get unique speakers
  const speakers = new Set();
  allRecordings.forEach(recording => {
    if (recording.speaker_names && Array.isArray(recording.speaker_names)) {
      recording.speaker_names.forEach(name => speakers.add(name));
    }
  });
  
  // Keep "All Speakers" option and add speakers alphabetically with person icon
  const currentValue = speakerSelect.value;
  speakerSelect.innerHTML = '<option value="">All Speakers</option>';
  Array.from(speakers).sort().forEach(speaker => {
    const option = document.createElement('option');
    option.value = speaker;
    option.textContent = `👤 ${speaker}`;
    speakerSelect.appendChild(option);
  });
  
  // Restore previous selection if it still exists
  if (currentValue && Array.from(speakers).includes(currentValue)) {
    speakerSelect.value = currentValue;
  }
}

// Apply all active filters and search
function applyFilters() {
  const searchInput = document.getElementById('search-input')?.value.toLowerCase() || '';
  const searchField = document.getElementById('search-field')?.value || 'title';
  const filterSpeaker = document.getElementById('filter-speaker')?.value || '';
  const filterCategory = document.getElementById('filter-category')?.value || '';
  
  const recordingList = document.getElementById('recording-list');
  if (!recordingList) return;
  
  recordingList.innerHTML = '';
  
  // Filter recordings
  const filtered = allRecordings.filter(recording => {
    const metadata = typeof recording === 'object' ? recording : {};
    const filename = typeof recording === 'string' ? recording : recording.filename;
    
    // Search filter
    if (searchInput) {
      let searchMatch = false;
      
      if (searchField === 'title' || searchField === 'both') {
        const title = (metadata.title || filename).toLowerCase();
        if (title.includes(searchInput)) searchMatch = true;
      }
      
      if (searchField === 'transcript' || searchField === 'both') {
        const transcript = (metadata.transcription || '').toLowerCase();
        if (transcript.includes(searchInput)) searchMatch = true;
      }
      
      if (!searchMatch) return false;
    }
    
    // Speaker filter
    if (filterSpeaker) {
      const speakers = metadata.speaker_names || [];
      if (!speakers.includes(filterSpeaker)) return false;
    }
    
    // Category filter
    if (filterCategory) {
      if (metadata.category !== filterCategory) return false;
    }
    
    return true;
  });
  
  // Update results count
  const resultsCount = document.getElementById('results-count');
  if (resultsCount) {
    if (filtered.length === allRecordings.length) {
      resultsCount.textContent = `${filtered.length} recording${filtered.length !== 1 ? 's' : ''}`;
    } else {
      resultsCount.textContent = `${filtered.length} of ${allRecordings.length} recording${allRecordings.length !== 1 ? 's' : ''}`;
    }
  }
  
  // Display filtered recordings
  if (filtered.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `
      <td colspan="5" class="py-8 text-center">
        <div class="flex flex-col items-center">
          <i class="fas fa-search text-4xl text-gray-300 dark:text-gray-600 mb-3"></i>
          <p class="text-gray-500 dark:text-gray-400">No recordings match your filters.</p>
          <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Try adjusting your search or filters.</p>
        </div>
      </td>
    `;
    recordingList.appendChild(emptyRow);
  } else {
    filtered.forEach(recording => {
      const item = createRecordingItem(recording);
      recordingList.appendChild(item);
    });
  }
  
  // Setup event listeners for the new items
  try {
    setupEventListeners();
  } catch (err) {
    console.error('Error in setupEventListeners:', err);
  }
  
  // Initialize audio players
  try {
    const isLargeDesktop = window.matchMedia && window.matchMedia('(min-width: 1024px)').matches;
    const audioElements = document.querySelectorAll('audio');
    
    if (isLargeDesktop) {
      Array.from(audioElements).map(p => {
        p.preload = 'metadata';
        const player = new Plyr(p, {
          controls: ['play', 'progress', 'current-time', 'duration'],
          displayDuration: true,
          hideControls: false,
          invertTime: false,
          seekTime: 5,
          tooltips: { controls: false, seek: false },
          fullscreen: { enabled: false },
          keyboard: { focused: true, global: false }
        });
        
        player.on('timeupdate', () => {
          const currentTimeEl = player.elements.container.querySelector('.plyr__time--current');
          const durationEl = player.elements.container.querySelector('.plyr__time--duration');
          
          if (currentTimeEl && isFinite(player.currentTime)) {
            currentTimeEl.textContent = formatTime(player.currentTime);
          }
          if (durationEl && isFinite(player.duration)) {
            durationEl.textContent = formatTime(player.duration);
          }
        });
        
        return player;
      });
    } else {
      Array.from(audioElements).forEach(p => { p.preload = 'metadata'; });
    }
    
    improveAudioDurationDetection();
  } catch (err) {
    console.error('Error initializing audio players:', err);
  }
}

// Initialize recordings on page load
document.addEventListener("DOMContentLoaded", function () {
  loadRecordings();
  
  // Setup filter event listeners
  const searchInput = document.getElementById('search-input');
  const searchField = document.getElementById('search-field');
  const filterSpeaker = document.getElementById('filter-speaker');
  const filterCategory = document.getElementById('filter-category');
  const clearFilters = document.getElementById('clear-filters');
  
  if (searchInput) {
    // Debounce search input - wait 300ms after user stops typing
    searchInput.addEventListener('input', () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        applyFilters();
      }, 300);
    });
  }
  
  if (searchField) {
    searchField.addEventListener('change', applyFilters);
  }
  
  if (filterSpeaker) {
    filterSpeaker.addEventListener('change', applyFilters);
  }
  
  if (filterCategory) {
    filterCategory.addEventListener('change', applyFilters);
  }
  
  if (clearFilters) {
    clearFilters.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      if (searchField) searchField.value = 'title';
      if (filterSpeaker) filterSpeaker.value = '';
      if (filterCategory) filterCategory.value = '';
      applyFilters();
    });
  }
});
