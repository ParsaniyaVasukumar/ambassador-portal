(function () {
  const data = window.SUMMARY_DATA || {};
  const brandRed = '#e8382b';
  const palette = ['#e8382b', '#ff5a45', '#c22a1f', '#ffb8b0', '#9c2018', '#6b7280'];

  const stateSkeleton = document.getElementById('byStateSkeleton');
  const profileSkeleton = document.getElementById('byProfileSkeleton');

  if (typeof Chart === 'undefined') {
    // Chart.js failed to load from the CDN (e.g. offline) — fail gracefully
    // instead of leaving skeletons spinning forever.
    [stateSkeleton, profileSkeleton].forEach(el => {
      if (el) el.innerHTML = '<p class="text-sm text-ink-500 m-auto">Charts unavailable — check your connection.</p>';
    });
    return;
  }

  const stateCtx = document.getElementById('byStateChart');
  if (stateCtx && data.by_state && data.by_state.length) {
    new Chart(stateCtx, {
      type: 'bar',
      data: {
        labels: data.by_state.map(s => s.state_display),
        datasets: [{ label: 'Ambassadors', data: data.by_state.map(s => s.count), backgroundColor: brandRed, borderRadius: 4 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    });
    stateSkeleton?.remove();
  } else if (stateSkeleton) {
    stateSkeleton.innerHTML = '<p class="text-sm text-ink-500 m-auto">No state data yet</p>';
  }

  const profileCtx = document.getElementById('byProfileChart');
  if (profileCtx && data.by_profile && data.by_profile.length) {
    new Chart(profileCtx, {
      type: 'doughnut',
      data: {
        labels: data.by_profile.map(p => p.profile),
        datasets: [{ data: data.by_profile.map(p => p.count), backgroundColor: palette }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
    });
    profileSkeleton?.remove();
  } else if (profileSkeleton) {
    profileSkeleton.innerHTML = '<p class="text-sm text-ink-500 m-auto">No profile data yet</p>';
  }
})();