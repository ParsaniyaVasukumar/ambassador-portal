(function () {
  const body = document.getElementById('rosterBody');
  const emptyState = document.getElementById('emptyState');
  const resultCount = document.getElementById('resultCount');
  const searchInput = document.getElementById('searchInput');
  const stateFilter = document.getElementById('stateFilter');
  const profileFilter = document.getElementById('profileFilter');
  const clearBtn = document.getElementById('clearFilters');
  const sortHeaders = document.querySelectorAll('th[data-sort]');

  let sortBy = 'sr_no';
  let sortDir = 'asc';
  let debounceTimer;
  let isFirstLoad = true;

  // Prefill from URL params (so links from the header search / coverage map / homepage work)
  const params = new URLSearchParams(window.location.search);
  const arrivedViaSearch = !!params.get('search');
  if (params.get('search')) searchInput.value = params.get('search');
  if (params.get('state')) stateFilter.value = params.get('state');
  if (params.get('profile')) profileFilter.value = params.get('profile');

  function badge(quality) {
    if (quality >= 80) return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">${quality}%</span>`;
    if (quality >= 50) return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">${quality}%</span>`;
    return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">${quality}%</span>`;
  }

  function updateSortIndicators() {
    sortHeaders.forEach(th => {
      const col = th.dataset.sort;
      const base = th.textContent.replace(/ ↑| ↓/g, '');
      th.textContent = base + (col === sortBy ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '');
    });
  }

  function render(rows) {
    body.innerHTML = '';
    emptyState.classList.toggle('hidden', rows.length > 0);
    resultCount.textContent = `${rows.length} ambassador${rows.length === 1 ? '' : 's'}`;
    rows.forEach(r => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-neutral-50 transition-colors duration-700';
      tr.dataset.code = r.ambassador_code;
      tr.innerHTML = `
        <td class="px-4 py-3 text-ink-500">${r.sr_no ?? ''}</td>
        <td class="px-4 py-3 font-medium">${r.name || '—'}</td>
        <td class="px-4 py-3">${r.brand_name || '—'}</td>
        <td class="px-4 py-3 font-mono text-xs text-ink-500">${r.ambassador_code}</td>
        <td class="px-4 py-3">${r.city || '—'}</td>
        <td class="px-4 py-3">${r.state_display}</td>
        <td class="px-4 py-3">
          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-ink-700">${r.profile}</span>
        </td>
        <td class="px-4 py-3">${badge(r.completeness)}</td>
      `;
      body.appendChild(tr);
    });
  }

  // When arriving from a search (header bar, homepage, or a shared link), scroll to
  // the results and briefly flash them so it's obvious what was "found" rather than
  // just silently filtering the table.
  function highlightResults() {
    const rows = body.querySelectorAll('tr');
    if (!rows.length) return;
    rows[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    rows.forEach(tr => {
      tr.classList.add('bg-brand-50');
      setTimeout(() => tr.classList.remove('bg-brand-50'), 1800);
    });
  }

  async function load() {
    const q = new URLSearchParams({
      search: searchInput.value.trim(),
      state: stateFilter.value,
      profile: profileFilter.value,
      sort_by: sortBy,
      sort_dir: sortDir,
    });
    const res = await fetch(`/api/ambassadors?${q.toString()}`);
    const rows = await res.json();
    render(rows);
    updateSortIndicators();

    if (isFirstLoad && arrivedViaSearch && rows.length) {
      highlightResults();
    }
    isFirstLoad = false;

    // Reflect current filters in the URL so the view is shareable/bookmarkable
    const urlParams = new URLSearchParams();
    if (searchInput.value.trim()) urlParams.set('search', searchInput.value.trim());
    if (stateFilter.value) urlParams.set('state', stateFilter.value);
    if (profileFilter.value) urlParams.set('profile', profileFilter.value);
    const qs = urlParams.toString();
    history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
  }

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(load, 200);
  });
  stateFilter.addEventListener('change', load);
  profileFilter.addEventListener('change', load);
  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    stateFilter.value = '';
    profileFilter.value = '';
    sortBy = 'sr_no';
    sortDir = 'asc';
    load();
  });

  sortHeaders.forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortBy === col) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortBy = col;
        sortDir = 'asc';
      }
      load();
    });
  });

  load();
})();