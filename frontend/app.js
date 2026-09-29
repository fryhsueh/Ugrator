document.addEventListener('DOMContentLoaded', () => {
    // Two-Tier Modular Tab switching logic with LocalStorage persistence
    const moduleBtns = document.querySelectorAll('.module-btn');
    const subNavGroups = document.querySelectorAll('.sub-nav-group');
    const subTabBtns = document.querySelectorAll('.sub-tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    function activateTab(moduleId, targetTabId) {
        // 1. Activate Tier 1 module button
        moduleBtns.forEach(btn => {
            if (btn.dataset.module === moduleId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 2. Show corresponding sub-nav group
        subNavGroups.forEach(group => {
            if (group.id === `subnav-${moduleId}`) {
                group.style.display = 'flex';
                group.classList.add('active');
            } else {
                group.style.display = 'none';
                group.classList.remove('active');
            }
        });

        // 3. Find sub-tab button to activate
        const activeGroup = document.getElementById(`subnav-${moduleId}`);
        if (!activeGroup) return;

        let activeSubBtn = targetTabId ? activeGroup.querySelector(`[data-target="${targetTabId}"]`) : null;
        if (!activeSubBtn) {
            // Default to first sub-button in this group
            activeSubBtn = activeGroup.querySelector('.sub-tab-btn');
        }

        if (activeSubBtn) {
            subTabBtns.forEach(b => b.classList.remove('active'));
            activeSubBtn.classList.add('active');
            targetTabId = activeSubBtn.dataset.target;
        }

        // 4. Show corresponding tab content
        tabContents.forEach(c => {
            c.style.display = '';
            if (c.id === targetTabId) {
                c.classList.add('active');
            } else {
                c.classList.remove('active');
            }
        });

        // 5. Persist state in localStorage
        if (moduleId && targetTabId) {
            localStorage.setItem('ugrator_active_module', moduleId);
            localStorage.setItem('ugrator_active_subtab', targetTabId);
        }
    }

    // Module Click handler
    moduleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const moduleId = btn.dataset.module;
            activateTab(moduleId, null);
        });
    });

    // Sub-tab Click handler
    subTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const parentGroup = btn.closest('.sub-nav-group');
            const moduleId = parentGroup ? parentGroup.id.replace('subnav-', '') : 'tickets';
            const targetId = btn.dataset.target;
            activateTab(moduleId, targetId);
        });
    });

    // Restore saved module & sub-tab on page load / F5
    const savedModule = localStorage.getItem('ugrator_active_module') || 'tickets';
    const savedSubtab = localStorage.getItem('ugrator_active_subtab') || 'tab-fields';
    activateTab(savedModule, savedSubtab);

    // Global Authentication Script input
    const globalAuthScriptInput = document.getElementById('global-auth-script');

    // Drag and drop logic for textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('dragover', (e) => {
            e.preventDefault();
            textarea.classList.add('drag-over');
        });
        textarea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            textarea.classList.remove('drag-over');
        });
        textarea.addEventListener('drop', (e) => {
            e.preventDefault();
            textarea.classList.remove('drag-over');

            const file = e.dataTransfer.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                textarea.value = e.target.result;
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
            };
            reader.readAsText(file);
        });
    });

    // Console output logic
    const consoleOutput = document.getElementById('console-output');
    const btnClearConsole = document.getElementById('btn-clear-console');

    function logToConsole(message, type = 'system') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;

        // Prefix with timestamp
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];
        entry.textContent = `[${timeStr}] ${message}`;

        consoleOutput.appendChild(entry);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    btnClearConsole.addEventListener('click', () => {
        consoleOutput.innerHTML = '';
        logToConsole('Console cleared.', 'system');
    });

    // ==========================================================================
    // Multi-Domain Tenant Switcher & Workspace Isolation
    // ==========================================================================
    const TenantProfileManager = (() => {
        const STORAGE_KEY = 'ugrator_profiles_v1';
        const LEGACY_AUTH_KEY = 'saved_state_global-auth-script';

        let state = {
            activeDomain: null,
            profiles: {}
        };

        let isCreatingNew = false;

        // Elements
        const domainBadge = document.getElementById('domain-badge');
        const domainSelectorBtn = document.getElementById('domain-selector-btn');
        const domainDropdownMenu = document.getElementById('domain-dropdown-menu');
        const domainDropdownList = document.getElementById('domain-dropdown-list');
        const btnAddDomain = document.getElementById('btn-add-domain');
        const btnClearSession = document.getElementById('btn-clear-session');
        const selectPresetTenantA = document.getElementById('select-preset-tenant-a');
        const selectPresetTenantB = document.getElementById('select-preset-tenant-b');

        function getTrackedElements() {
            return document.querySelectorAll('textarea, input.form-input');
        }

        function extractDomain(script) {
            if (!script) return null;
            // 1. Match -Uri with quotes or without quotes
            const uriMatch = script.match(/-Uri\s+["']?https?:\/\/([^/'"\s]+)/i);
            if (uriMatch && uriMatch[1]) return uriMatch[1].trim();
            // 2. Match any http(s) host
            const hostMatch = script.match(/https?:\/\/([^/'"\s]+)/i);
            if (hostMatch && hostMatch[1]) return hostMatch[1].trim();
            // 3. Match any domain in cookies/headers
            const cookieDomainMatch = script.match(/\.([a-zA-Z0-9_-]+\.[a-zA-Z]{2,})/i);
            if (cookieDomainMatch && cookieDomainMatch[1]) return cookieDomainMatch[1].trim();
            return null;
        }

        function loadFromStorage() {
            try {
                const raw = localStorage.getItem(STORAGE_KEY);
                if (raw) {
                    state = JSON.parse(raw);
                    if (!state.profiles) state.profiles = {};
                    if (Object.keys(state.profiles).length > 0) {
                        if (!state.activeDomain || !state.profiles[state.activeDomain]) {
                            state.activeDomain = Object.keys(state.profiles)[0];
                        }
                        return;
                    }
                }
            } catch (e) {
                console.error('Error reading tenant profiles:', e);
            }

            // Backward Compatibility: Scan localStorage for any legacy saved_state_* keys
            const legacyInputs = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith('saved_state_')) {
                    const elId = key.replace('saved_state_', '');
                    const val = localStorage.getItem(key);
                    if (val) legacyInputs[elId] = val;
                }
            }

            const legacyAuth = legacyInputs['global-auth-script'] || localStorage.getItem(LEGACY_AUTH_KEY) || '';
            const detectedDomain = extractDomain(legacyAuth) || (Object.keys(legacyInputs).length > 0 ? 'default' : null);

            if (detectedDomain) {
                state = {
                    activeDomain: detectedDomain,
                    profiles: {
                        [detectedDomain]: {
                            domain: detectedDomain,
                            authScript: legacyAuth || '',
                            inputs: legacyInputs,
                            updatedAt: Date.now()
                        }
                    }
                };
                saveToStorage();
            } else {
                state = {
                    activeDomain: null,
                    profiles: {}
                };
            }
        }

        function saveToStorage() {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
            } catch (e) {
                console.error('Error saving tenant profiles:', e);
            }
        }

        function syncCurrentDomToProfile() {
            if (isCreatingNew || !state.activeDomain) return;
            const profile = state.profiles[state.activeDomain];
            if (!profile) return;

            if (!profile.inputs) profile.inputs = {};
            getTrackedElements().forEach(el => {
                if (!el.id) return;
                profile.inputs[el.id] = el.value;
                try {
                    localStorage.setItem(`saved_state_${el.id}`, el.value);
                } catch (_) { }
            });
            profile.authScript = globalAuthScriptInput ? globalAuthScriptInput.value : '';
            if (globalAuthScriptInput) {
                try {
                    localStorage.setItem(LEGACY_AUTH_KEY, globalAuthScriptInput.value);
                } catch (_) { }
            }
            profile.updatedAt = Date.now();
            saveToStorage();
        }

        function applyProfileToDom(domain) {
            const profile = state.profiles[domain];
            if (!profile) return;

            if (globalAuthScriptInput) {
                globalAuthScriptInput.value = profile.authScript || '';
            }

            getTrackedElements().forEach(el => {
                if (!el.id || el.id === 'global-auth-script') return;
                let savedVal = (profile.inputs && profile.inputs[el.id] !== undefined) ? profile.inputs[el.id] : null;

                // Defensive Fallback: If IVR YAML input has no saved content in this profile, preserve default template
                if (el.id === 'ivr-yaml-input' && (!savedVal || !savedVal.trim())) {
                    savedVal = (typeof IVR_TEMPLATES !== 'undefined' && IVR_TEMPLATES.multilang_multicanvas) ? IVR_TEMPLATES.multilang_multicanvas : el.value;
                }

                if (savedVal !== null) {
                    el.value = savedVal;
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
            });

            try {
                if (typeof loadGridFromProfile === 'function') {
                    loadGridFromProfile();
                }
                if (typeof loadCustomerGridFromProfile === 'function') {
                    loadCustomerGridFromProfile();
                }
            } catch (err) {
                console.error('Error loading grid from profile:', err);
            }

            updateUiDisplay();
        }

        function updateUiDisplay() {
            if (isCreatingNew) {
                if (domainBadge) domainBadge.textContent = 'Domain: [New Tenant...]';
            } else if (state.activeDomain) {
                if (domainBadge) domainBadge.textContent = `Domain: ${state.activeDomain}`;
            } else {
                if (domainBadge) domainBadge.textContent = 'Domain: None';
            }

            renderDropdownList();
            renderPresetSelects();
        }

        function renderDropdownList() {
            if (!domainDropdownList) return;
            domainDropdownList.innerHTML = '';

            const domains = Object.keys(state.profiles);
            if (domains.length === 0) {
                const emptyEl = document.createElement('div');
                emptyEl.style.padding = '8px 14px';
                emptyEl.style.fontSize = '0.8rem';
                emptyEl.style.color = '#64748b';
                emptyEl.textContent = 'No saved domains. Click "+ New Domain" to add one.';
                domainDropdownList.appendChild(emptyEl);
                return;
            }

            domains.forEach(domain => {
                const item = document.createElement('div');
                item.className = 'domain-item' + (domain === state.activeDomain && !isCreatingNew ? ' active' : '');

                const nameSpan = document.createElement('span');
                nameSpan.className = 'domain-item-name';
                nameSpan.textContent = domain;
                nameSpan.title = domain;

                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'domain-item-actions';

                if (domain === state.activeDomain && !isCreatingNew) {
                    const checkSpan = document.createElement('span');
                    checkSpan.className = 'domain-item-check';
                    checkSpan.textContent = '✓';
                    actionsDiv.appendChild(checkSpan);
                }

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'domain-item-delete';
                deleteBtn.textContent = '✕';
                deleteBtn.title = `Delete ${domain}`;
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteDomain(domain);
                });
                actionsDiv.appendChild(deleteBtn);

                item.appendChild(nameSpan);
                item.appendChild(actionsDiv);

                item.addEventListener('click', () => {
                    switchToDomain(domain);
                    closeDropdown();
                });

                domainDropdownList.appendChild(item);
            });
        }

        function renderPresetSelects() {
            const domains = Object.keys(state.profiles);
            const selects = [selectPresetTenantA, selectPresetTenantB];

            selects.forEach(select => {
                if (!select) return;
                select.innerHTML = '<option value="">Load from saved domain...</option>';
                domains.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d;
                    opt.textContent = d;
                    select.appendChild(opt);
                });
                select.value = '';
            });
        }

        function switchToDomain(targetDomain) {
            if (!state.profiles[targetDomain]) return;
            if (state.activeDomain === targetDomain && !isCreatingNew) return;

            syncCurrentDomToProfile();

            isCreatingNew = false;
            state.activeDomain = targetDomain;
            saveToStorage();

            applyProfileToDom(targetDomain);
            logToConsole(`Switched active tenant to: ${targetDomain}`, 'system');
        }

        function startNewDomainFlow() {
            syncCurrentDomToProfile();
            isCreatingNew = true;
            state.activeDomain = null;

            if (globalAuthScriptInput) {
                globalAuthScriptInput.value = '';
                globalAuthScriptInput.focus();
            }
            getTrackedElements().forEach(el => {
                if (el.id !== 'global-auth-script') {
                    el.value = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
            gridRows = [];
            if (typeof renderGrid === 'function') renderGrid();

            updateUiDisplay();
            closeDropdown();
            logToConsole('Ready for new tenant. Paste the PowerShell request for the new domain into the Global Authentication Script.', 'system');
        }

        function deleteDomain(domainToDelete) {
            if (!confirm(`Are you sure you want to delete tenant profile "${domainToDelete}"?\nAll saved drafts for this tenant will be removed.`)) {
                return;
            }

            delete state.profiles[domainToDelete];

            if (state.activeDomain === domainToDelete) {
                const remaining = Object.keys(state.profiles);
                if (remaining.length > 0) {
                    state.activeDomain = remaining[0];
                    saveToStorage();
                    applyProfileToDom(state.activeDomain);
                } else {
                    state.activeDomain = null;
                    isCreatingNew = true;
                    saveToStorage();
                    if (globalAuthScriptInput) globalAuthScriptInput.value = '';
                    getTrackedElements().forEach(el => el.value = '');
                    gridRows = [];
                    if (typeof renderGrid === 'function') renderGrid();
                    updateUiDisplay();
                }
            } else {
                saveToStorage();
                updateUiDisplay();
            }

            logToConsole(`Tenant profile "${domainToDelete}" deleted.`, 'system');
        }

        function clearActiveSession() {
            const domainLabel = isCreatingNew ? 'Pending New Tenant' : (state.activeDomain || 'Current');
            if (!confirm(`Are you sure you want to clear inputs and script for domain "${domainLabel}"?\nOther saved tenant profiles will NOT be affected.`)) {
                return;
            }

            if (globalAuthScriptInput) globalAuthScriptInput.value = '';
            getTrackedElements().forEach(el => {
                if (el.id !== 'global-auth-script') {
                    el.value = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
            gridRows = [];
            if (typeof renderGrid === 'function') renderGrid();

            if (state.activeDomain && state.profiles[state.activeDomain]) {
                state.profiles[state.activeDomain].authScript = '';
                state.profiles[state.activeDomain].inputs = {};
                state.profiles[state.activeDomain].updatedAt = Date.now();
                saveToStorage();
            }

            updateUiDisplay();
            logToConsole(`Cleared inputs for ${domainLabel}.`, 'system');
        }

        function handleAuthScriptInput() {
            const script = globalAuthScriptInput ? globalAuthScriptInput.value : '';
            const detectedDomain = extractDomain(script);

            // Dual-write fallback to legacy key
            try {
                localStorage.setItem(LEGACY_AUTH_KEY, script);
            } catch (_) { }

            if (isCreatingNew) {
                if (detectedDomain) {
                    if (!state.profiles[detectedDomain]) {
                        state.profiles[detectedDomain] = {
                            domain: detectedDomain,
                            authScript: script,
                            inputs: {},
                            updatedAt: Date.now()
                        };
                    } else {
                        state.profiles[detectedDomain].authScript = script;
                    }
                    state.activeDomain = detectedDomain;
                    isCreatingNew = false;
                    saveToStorage();
                    updateUiDisplay();
                    logToConsole(`New tenant domain registered: ${detectedDomain}`, 'success');
                }
            } else if (state.activeDomain) {
                const profile = state.profiles[state.activeDomain];
                if (profile) {
                    profile.authScript = script;
                    profile.updatedAt = Date.now();
                    // If activeDomain was 'default' and we now detected a specific domain, upgrade profile key
                    if (state.activeDomain === 'default' && detectedDomain && detectedDomain !== 'default') {
                        delete state.profiles['default'];
                        profile.domain = detectedDomain;
                        state.profiles[detectedDomain] = profile;
                        state.activeDomain = detectedDomain;
                        updateUiDisplay();
                        logToConsole(`Updated tenant profile domain to: ${detectedDomain}`, 'success');
                    }
                    saveToStorage();
                }
                if (detectedDomain && detectedDomain !== state.activeDomain) {
                    logToConsole(`Notice: Pasted script matches domain "${detectedDomain}" (Active profile: "${state.activeDomain}"). Use "+ New Domain" in the switcher to register a separate profile.`, 'warn');
                }
            } else {
                const targetDomain = detectedDomain || (script.trim() ? 'default' : null);
                if (targetDomain) {
                    if (!state.profiles[targetDomain]) {
                        state.profiles[targetDomain] = {
                            domain: targetDomain,
                            authScript: script,
                            inputs: {},
                            updatedAt: Date.now()
                        };
                    } else {
                        state.profiles[targetDomain].authScript = script;
                    }
                    state.activeDomain = targetDomain;
                    saveToStorage();
                    updateUiDisplay();
                    logToConsole(`Tenant domain registered: ${targetDomain}`, 'success');
                }
            }
        }

        function toggleDropdown() {
            if (!domainDropdownMenu) return;
            const isOpen = domainDropdownMenu.style.display === 'block';
            if (isOpen) {
                closeDropdown();
            } else {
                domainDropdownMenu.style.display = 'block';
                if (domainSelectorBtn) domainSelectorBtn.classList.add('open');
            }
        }

        function closeDropdown() {
            if (domainDropdownMenu) domainDropdownMenu.style.display = 'none';
            if (domainSelectorBtn) domainSelectorBtn.classList.remove('open');
        }

        function init() {
            loadFromStorage();

            if (state.activeDomain && state.profiles[state.activeDomain]) {
                applyProfileToDom(state.activeDomain);
            } else if (Object.keys(state.profiles).length > 0) {
                state.activeDomain = Object.keys(state.profiles)[0];
                saveToStorage();
                applyProfileToDom(state.activeDomain);
            } else if (globalAuthScriptInput && globalAuthScriptInput.value.trim()) {
                handleAuthScriptInput();
            } else {
                updateUiDisplay();
            }

            if (globalAuthScriptInput) {
                globalAuthScriptInput.addEventListener('input', handleAuthScriptInput);
            }

            getTrackedElements().forEach(el => {
                if (el.id === 'global-auth-script') return;
                el.addEventListener('input', () => {
                    // Dual-write fallback
                    try {
                        localStorage.setItem(`saved_state_${el.id}`, el.value);
                    } catch (_) { }

                    if (state.activeDomain && state.profiles[state.activeDomain]) {
                        if (!state.profiles[state.activeDomain].inputs) state.profiles[state.activeDomain].inputs = {};
                        state.profiles[state.activeDomain].inputs[el.id] = el.value;
                        state.profiles[state.activeDomain].updatedAt = Date.now();
                        saveToStorage();
                    }
                });
            });

            if (domainSelectorBtn) {
                domainSelectorBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleDropdown();
                });
            }

            document.addEventListener('click', (e) => {
                const wrapper = document.getElementById('domain-selector-wrapper');
                if (wrapper && !wrapper.contains(e.target)) {
                    closeDropdown();
                }
            });

            if (btnAddDomain) {
                btnAddDomain.addEventListener('click', (e) => {
                    e.stopPropagation();
                    startNewDomainFlow();
                });
            }

            if (btnClearSession) {
                btnClearSession.addEventListener('click', () => {
                    clearActiveSession();
                });
            }

            if (selectPresetTenantA) {
                selectPresetTenantA.addEventListener('change', () => {
                    const domain = selectPresetTenantA.value;
                    if (!domain) return;
                    const profile = state.profiles[domain];
                    const tAuthA = document.getElementById('t-auth-a');
                    if (profile && tAuthA) {
                        tAuthA.value = profile.authScript || '';
                        tAuthA.dispatchEvent(new Event('input', { bubbles: true }));
                        logToConsole(`Loaded Tenant A save script from profile: ${domain}`, 'system');
                    }
                    selectPresetTenantA.value = '';
                });
            }

            if (selectPresetTenantB) {
                selectPresetTenantB.addEventListener('change', () => {
                    const domain = selectPresetTenantB.value;
                    if (!domain) return;
                    const profile = state.profiles[domain];
                    const tAuthB = document.getElementById('t-auth-b');
                    if (profile && tAuthB) {
                        tAuthB.value = profile.authScript || '';
                        tAuthB.dispatchEvent(new Event('input', { bubbles: true }));
                        logToConsole(`Loaded Tenant B save script from profile: ${domain}`, 'system');
                    }
                    selectPresetTenantB.value = '';
                });
            }
        }

        return {
            init,
            getActiveDomain: () => state.activeDomain,
            getProfiles: () => state.profiles,
            syncCurrentDomToProfile
        };
    })();

    // ==========================================================================
    // Fetch Current Custom Fields Logic
    // ==========================================================================
    const btnFetchCustomFields = document.getElementById('btn-fetch-custom-fields');
    const fFetchedJson = document.getElementById('f-fetched-json');
    const fetchFieldsStats = document.getElementById('fetch-fields-stats');
    const btnCopyFetchedFields = document.getElementById('btn-copy-fetched-fields');
    const btnDownloadFetchedFields = document.getElementById('btn-download-fetched-fields');
    const btnSendToMigrate = document.getElementById('btn-send-to-migrate');

    function renderFieldStats(count, stats) {
        if (!fetchFieldsStats) return;
        fetchFieldsStats.innerHTML = '';
        if (count === undefined || count === null) {
            fetchFieldsStats.style.display = 'none';
            return;
        }

        fetchFieldsStats.style.display = 'flex';
        const totalChip = document.createElement('span');
        totalChip.className = 'stat-chip stat-total';
        totalChip.textContent = `Total: ${count}`;
        fetchFieldsStats.appendChild(totalChip);

        if (stats && typeof stats === 'object') {
            Object.entries(stats).forEach(([type, cnt]) => {
                const chip = document.createElement('span');
                chip.className = 'stat-chip';
                chip.textContent = `${type}: ${cnt}`;
                fetchFieldsStats.appendChild(chip);
            });
        }
    }

    if (btnFetchCustomFields) {
        btnFetchCustomFields.addEventListener('click', async () => {
            const authScript = document.getElementById('global-auth-script').value.trim();
            if (!authScript) {
                logToConsole('Error: Please paste your Global Authentication Script first.', 'error');
                return;
            }

            btnFetchCustomFields.disabled = true;
            btnFetchCustomFields.textContent = 'Fetching Fields from Tenant...';
            logToConsole('Fetching custom fields from Web Admin API...', 'system');

            try {
                const res = await fetch('/api/fetch-custom-fields', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ auth_script: authScript })
                });

                const result = await res.json();
                if (result.success) {
                    if (fFetchedJson) {
                        fFetchedJson.value = JSON.stringify(result.fields_json, null, 2);
                        fFetchedJson.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    renderFieldStats(result.count, result.stats);
                    logToConsole(result.message, 'success');
                } else {
                    logToConsole(`Error: ${result.message}`, 'error');
                }
            } catch (err) {
                logToConsole(`Failed fetching custom fields: ${err.message}`, 'error');
            } finally {
                btnFetchCustomFields.disabled = false;
                btnFetchCustomFields.textContent = 'Fetch Current Custom Fields from Tenant';
            }
        });
    }

    if (btnCopyFetchedFields && fFetchedJson) {
        btnCopyFetchedFields.addEventListener('click', async () => {
            const text = fFetchedJson.value.trim();
            if (!text) {
                logToConsole('No JSON to copy. Please fetch custom fields first.', 'warn');
                return;
            }
            try {
                await navigator.clipboard.writeText(text);
                logToConsole('Custom fields JSON copied to clipboard.', 'success');
            } catch {
                fFetchedJson.select();
                document.execCommand('copy');
                logToConsole('Custom fields JSON copied to clipboard.', 'success');
            }
        });
    }

    if (btnDownloadFetchedFields && fFetchedJson) {
        btnDownloadFetchedFields.addEventListener('click', () => {
            const text = fFetchedJson.value.trim();
            if (!text) {
                logToConsole('No JSON to download. Please fetch custom fields first.', 'warn');
                return;
            }
            const activeDomain = TenantProfileManager.getActiveDomain() || 'tenant';
            const blob = new Blob([text], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `custom_fields_${activeDomain}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            logToConsole(`Downloaded custom_fields_${activeDomain}.json.`, 'system');
        });
    }

    if (btnSendToMigrate && fFetchedJson) {
        btnSendToMigrate.addEventListener('click', () => {
            const text = fFetchedJson.value.trim();
            if (!text) {
                logToConsole('No JSON to transfer. Please fetch custom fields first.', 'warn');
                return;
            }
            const fRaw = document.getElementById('f-raw');
            if (fRaw) {
                fRaw.value = text;
                fRaw.dispatchEvent(new Event('input', { bubbles: true }));
            }
            const migrateTabBtn = document.querySelector('.sub-tab-btn[data-target="tab-fields"]');
            if (migrateTabBtn) {
                migrateTabBtn.click();
            }
            logToConsole('Transferred custom fields JSON to Migrate tab.', 'success');
        });
    }

    // ==========================================================================
    // Create Custom Fields (Dual Mode: Excel Upload / Table Grid) Logic
    // ==========================================================================
    const btnModeUpload = document.getElementById('btn-mode-upload');
    const btnModePaste = document.getElementById('btn-mode-paste');
    const panelModeUpload = document.getElementById('panel-mode-upload');
    const panelModePaste = document.getElementById('panel-mode-paste');
    const fieldsPasteTextarea = document.getElementById('fields-paste-textarea');
    const btnPasteSample = document.getElementById('btn-paste-sample');
    const btnPasteClear = document.getElementById('btn-paste-clear');
    const btnParsePaste = document.getElementById('btn-parse-paste');

    const excelDropZone = document.getElementById('excel-drop-zone');
    const fileFieldsInput = document.getElementById('file-fields-input');
    const btnBrowseExcel = document.getElementById('btn-browse-excel');
    const btnToolbarBrowse = document.getElementById('btn-toolbar-browse');
    const btnDownloadSampleExcel = document.getElementById('btn-download-sample-excel');
    const btnAddGridRow = document.getElementById('btn-add-grid-row');
    const btnClearGrid = document.getElementById('btn-clear-grid');
    const fieldGridTbody = document.getElementById('field-grid-tbody');
    const gridEmptyState = document.getElementById('grid-empty-state');
    const btnExecuteCreateFields = document.getElementById('btn-execute-create-fields');
    const badgeFieldsRolesStatus = document.getElementById('badge-fields-roles-status');
    const btnFetchFieldRoles = document.getElementById('btn-fetch-field-roles');
    const btnAddPersonaRule = document.getElementById('btn-add-persona-rule');
    const btnPresetRoleRules = document.getElementById('btn-preset-role-rules');
    const roleRulesList = document.getElementById('role-rules-list');

    let gridRows = [];
    let fieldTenantRoles = [];
    let personaRules = [
        { persona: 'Distributor', hiddenRoleIds: [] },
        { persona: 'Agent', hiddenRoleIds: [] }
    ];

    function savePersonaRulesToProfile() {
        const activeDomain = TenantProfileManager.getActiveDomain();
        if (activeDomain) {
            const profiles = TenantProfileManager.getProfiles();
            if (profiles[activeDomain]) {
                if (!profiles[activeDomain].inputs) profiles[activeDomain].inputs = {};
                profiles[activeDomain].inputs['persona_rules'] = JSON.stringify(personaRules);
            }
        }
        try {
            localStorage.setItem('saved_state_persona_rules', JSON.stringify(personaRules));
        } catch (_) { }
    }

    function loadPersonaRulesFromProfile() {
        const activeDomain = TenantProfileManager.getActiveDomain();
        let loaded = null;
        if (activeDomain) {
            const profiles = TenantProfileManager.getProfiles();
            if (profiles[activeDomain] && profiles[activeDomain].inputs && profiles[activeDomain].inputs['persona_rules']) {
                try {
                    loaded = JSON.parse(profiles[activeDomain].inputs['persona_rules']);
                } catch (_) { }
            }
        }
        if (!loaded) {
            try {
                const raw = localStorage.getItem('saved_state_persona_rules');
                if (raw) loaded = JSON.parse(raw);
            } catch (_) { }
        }
        if (Array.isArray(loaded) && loaded.length > 0) {
            personaRules = loaded;
        } else {
            personaRules = [
                { persona: 'Distributor', hiddenRoleIds: [] },
                { persona: 'Agent', hiddenRoleIds: [] }
            ];
        }
        renderPersonaRules();
    }

    async function fetchFieldTenantRoles(silent = false) {
        const authScript = document.getElementById('global-auth-script').value.trim();
        if (!authScript) {
            if (!silent) {
                logToConsole('Error: Please provide your Global Authentication Script first to load roles.', 'error');
            }
            return;
        }

        if (badgeFieldsRolesStatus) {
            badgeFieldsRolesStatus.textContent = 'Loading Roles...';
            badgeFieldsRolesStatus.className = 'badge-status badge-creating';
        }

        try {
            const resp = await fetch('/api/fetch-agent-metadata', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ auth_script: authScript })
            });

            const result = await resp.json();
            if (result.success && result.data && Array.isArray(result.data.roles)) {
                fieldTenantRoles = result.data.roles;
                if (badgeFieldsRolesStatus) {
                    badgeFieldsRolesStatus.textContent = `✓ ${fieldTenantRoles.length} Roles Loaded`;
                    badgeFieldsRolesStatus.className = 'badge-status badge-success';
                }
                if (!silent) {
                    logToConsole(`Loaded ${fieldTenantRoles.length} tenant roles for field visibility control.`, 'success');
                }
                renderPersonaRules();
                renderGrid();
            } else {
                if (badgeFieldsRolesStatus) {
                    badgeFieldsRolesStatus.textContent = '✕ Roles Failed';
                    badgeFieldsRolesStatus.className = 'badge-status badge-failed';
                }
                if (!silent) {
                    logToConsole(`Failed to load roles: ${result.message}`, 'error');
                }
            }
        } catch (err) {
            if (badgeFieldsRolesStatus) {
                badgeFieldsRolesStatus.textContent = '✕ Error';
                badgeFieldsRolesStatus.className = 'badge-status badge-failed';
            }
            if (!silent) {
                logToConsole(`Error loading roles: ${err.message}`, 'error');
            }
        }
    }

    if (btnFetchFieldRoles) {
        btnFetchFieldRoles.addEventListener('click', () => {
            fetchFieldTenantRoles(false);
        });
    }

    if (btnAddPersonaRule) {
        btnAddPersonaRule.addEventListener('click', () => {
            personaRules.push({
                persona: `Persona ${personaRules.length + 1}`,
                hiddenRoleIds: []
            });
            savePersonaRulesToProfile();
            renderPersonaRules();
            renderGrid();
        });
    }

    if (btnPresetRoleRules) {
        btnPresetRoleRules.addEventListener('click', async () => {
            if (fieldTenantRoles.length === 0) {
                await fetchFieldTenantRoles(true);
            }
            if (fieldTenantRoles.length === 0) {
                logToConsole('Please ensure Global Authentication Script is valid and roles can be fetched.', 'error');
                return;
            }

            // Find Agent and Distributor roles
            const agentRole = fieldTenantRoles.find(r => {
                const n = (r.name || '').toLowerCase();
                return (n.includes('agent') || n.includes('坐席') || n.includes('客服')) && !n.includes('super') && !n.includes('admin') && !n.includes('主管');
            }) || fieldTenantRoles.find(r => (r.name || '').toLowerCase().includes('agent'));

            const distRole = fieldTenantRoles.find(r => {
                const n = (r.name || '').toLowerCase();
                return n.includes('distributor') || n.includes('dealer') || n.includes('分销') || n.includes('经销商');
            });

            if (!agentRole || !distRole) {
                logToConsole(`Role Preset: Looked for Agent and Distributor roles. Available roles: ${fieldTenantRoles.map(r => r.name).join(', ')}. Please configure rules manually.`, 'warn');
                return;
            }

            personaRules = [
                { persona: 'Distributor', hiddenRoleIds: [agentRole.id] },
                { persona: 'Agent', hiddenRoleIds: [distRole.id] }
            ];

            savePersonaRulesToProfile();
            renderPersonaRules();
            renderGrid();
            logToConsole(`⚡ Applied Role Preset: 'Distributor' fields hidden for [${agentRole.name} (ID: ${agentRole.id})], 'Agent' fields hidden for [${distRole.name} (ID: ${distRole.id})].`, 'success');
        });
    }

    function renderPersonaRules() {
        if (!roleRulesList) return;
        roleRulesList.innerHTML = '';

        if (personaRules.length === 0) {
            roleRulesList.innerHTML = '<span style="color: #64748b; font-size: 0.82rem; font-style: italic;">No rules defined. Click "Add Rule" or "Role Preset" above.</span>';
            return;
        }

        personaRules.forEach((rule, rIdx) => {
            const rowDiv = document.createElement('div');
            rowDiv.className = 'role-rule-row';

            // 1. Persona Input
            const labelPersona = document.createElement('span');
            labelPersona.className = 'rule-persona-label';
            labelPersona.innerHTML = '👤 When Persona:';
            rowDiv.appendChild(labelPersona);

            const inputP = document.createElement('input');
            inputP.type = 'text';
            inputP.className = 'rule-persona-input';
            inputP.value = rule.persona || '';
            inputP.placeholder = 'e.g. Distributor';
            inputP.addEventListener('input', () => {
                rule.persona = inputP.value.trim();
                savePersonaRulesToProfile();
                renderGrid();
            });
            rowDiv.appendChild(inputP);

            // 2. Hide for roles label
            const labelHide = document.createElement('span');
            labelHide.className = 'rule-persona-label';
            labelHide.style.marginLeft = '8px';
            labelHide.innerHTML = '🚫 Hide for Roles:';
            rowDiv.appendChild(labelHide);

            // 3. Roles pills
            const selectorDiv = document.createElement('div');
            selectorDiv.className = 'rule-roles-selector';

            if (fieldTenantRoles.length === 0) {
                const hint = document.createElement('span');
                hint.style.color = '#64748b';
                hint.style.fontSize = '0.78rem';
                hint.style.fontStyle = 'italic';
                hint.textContent = '(Click "Refresh Roles" to load roles)';
                selectorDiv.appendChild(hint);
            } else {
                fieldTenantRoles.forEach(role => {
                    const pill = document.createElement('button');
                    pill.type = 'button';
                    const isHidden = Array.isArray(rule.hiddenRoleIds) && rule.hiddenRoleIds.includes(role.id);
                    pill.className = `role-badge-toggle ${isHidden ? 'is-hidden' : ''}`;
                    pill.textContent = `${isHidden ? '🚫 ' : ''}${role.name}`;
                    pill.title = isHidden ? `Hidden for ${role.name}. Click to make visible.` : `Visible for ${role.name}. Click to hide.`;
                    pill.addEventListener('click', () => {
                        if (!Array.isArray(rule.hiddenRoleIds)) rule.hiddenRoleIds = [];
                        if (rule.hiddenRoleIds.includes(role.id)) {
                            rule.hiddenRoleIds = rule.hiddenRoleIds.filter(id => id !== role.id);
                        } else {
                            rule.hiddenRoleIds.push(role.id);
                        }
                        savePersonaRulesToProfile();
                        renderPersonaRules();
                        renderGrid();
                    });
                    selectorDiv.appendChild(pill);
                });
            }
            rowDiv.appendChild(selectorDiv);

            // 4. Delete rule button
            const btnDel = document.createElement('button');
            btnDel.type = 'button';
            btnDel.className = 'btn-rule-delete';
            btnDel.innerHTML = '✕';
            btnDel.title = 'Remove this rule';
            btnDel.addEventListener('click', () => {
                personaRules.splice(rIdx, 1);
                savePersonaRulesToProfile();
                renderPersonaRules();
                renderGrid();
            });
            rowDiv.appendChild(btnDel);

            roleRulesList.appendChild(rowDiv);
        });
    }

    function getEffectiveInvisibleRoleIds(item) {
        if (Array.isArray(item.invisible_role_ids) && item.invisible_role_ids.length > 0) {
            return item.invisible_role_ids;
        }
        const persona = (item.persona || 'All').trim().toLowerCase();
        if (persona && persona !== 'all') {
            const rule = personaRules.find(r => r.persona && r.persona.trim().toLowerCase() === persona);
            if (rule && Array.isArray(rule.hiddenRoleIds) && rule.hiddenRoleIds.length > 0) {
                return rule.hiddenRoleIds;
            }
        }
        return [];
    }

    function renderRowHiddenBadges(container, item) {
        container.innerHTML = '';
        const invIds = getEffectiveInvisibleRoleIds(item);
        const wrapper = document.createElement('div');
        wrapper.style.display = 'flex';
        wrapper.style.alignItems = 'center';
        wrapper.style.flexWrap = 'wrap';
        wrapper.style.gap = '4px';

        if (invIds.length === 0) {
            const spanAll = document.createElement('span');
            spanAll.className = 'badge-role-all-visible';
            spanAll.textContent = fieldTenantRoles.length > 0 ? 'Visible to all' : '(Roles not loaded)';
            wrapper.appendChild(spanAll);
        } else {
            invIds.forEach(rId => {
                const roleObj = fieldTenantRoles.find(r => r.id === rId);
                const rName = roleObj ? roleObj.name : `Role ${rId}`;
                const b = document.createElement('span');
                b.className = 'badge-role-hidden';
                b.textContent = `🚫 ${rName}`;
                wrapper.appendChild(b);
            });
        }

        // Mini role picker button to customize per-row
        if (fieldTenantRoles.length > 0) {
            const btnPick = document.createElement('button');
            btnPick.type = 'button';
            btnPick.style.background = 'transparent';
            btnPick.style.border = 'none';
            btnPick.style.color = '#94a3b8';
            btnPick.style.cursor = 'pointer';
            btnPick.style.fontSize = '0.78rem';
            btnPick.style.padding = '2px 4px';
            btnPick.title = 'Custom role visibility override for this field';
            btnPick.textContent = '⚙️';
            btnPick.addEventListener('click', (e) => {
                e.stopPropagation();
                openRowRoleModal(item);
            });
            wrapper.appendChild(btnPick);
        }

        container.appendChild(wrapper);
    }

    function openRowRoleModal(item) {
        const currentInvIds = new Set(getEffectiveInvisibleRoleIds(item));
        const modalOverlay = document.createElement('div');
        modalOverlay.style.position = 'fixed';
        modalOverlay.style.top = '0';
        modalOverlay.style.left = '0';
        modalOverlay.style.width = '100vw';
        modalOverlay.style.height = '100vh';
        modalOverlay.style.background = 'rgba(0,0,0,0.6)';
        modalOverlay.style.display = 'flex';
        modalOverlay.style.alignItems = 'center';
        modalOverlay.style.justifyContent = 'center';
        modalOverlay.style.zIndex = '9999';

        const modalBox = document.createElement('div');
        modalBox.style.background = '#1e293b';
        modalBox.style.border = '1px solid rgba(255,255,255,0.15)';
        modalBox.style.borderRadius = '12px';
        modalBox.style.padding = '20px';
        modalBox.style.width = '360px';
        modalBox.style.maxWidth = '90vw';
        modalBox.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';

        modalBox.innerHTML = `
            <div style="font-size: 0.95rem; font-weight: 600; color: #f8fafc; margin-bottom: 6px;">
                Visibility: ${item.title || 'Untitled Field'}
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 14px;">
                Check the roles that should <b>NOT</b> be able to view this field:
            </div>
            <div id="modal-role-checkboxes" style="display: flex; flex-direction: column; gap: 8px; max-height: 200px; overflow-y: auto; margin-bottom: 16px;"></div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <button type="button" id="btn-modal-reset" class="btn-tool-secondary" style="font-size: 0.78rem;">Reset to Persona Rule</button>
                <button type="button" id="btn-modal-save" class="btn-tool" style="font-size: 0.82rem; background: #3b82f6; color: white;">Done</button>
            </div>
        `;

        const checkContainer = modalBox.querySelector('#modal-role-checkboxes');
        fieldTenantRoles.forEach(r => {
            const row = document.createElement('label');
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.gap = '8px';
            row.style.fontSize = '0.84rem';
            row.style.color = '#e2e8f0';
            row.style.cursor = 'pointer';

            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = r.id;
            chk.checked = currentInvIds.has(r.id);
            row.appendChild(chk);
            row.appendChild(document.createTextNode(`🚫 Hide for ${r.name}`));
            checkContainer.appendChild(row);
        });

        modalBox.querySelector('#btn-modal-reset').addEventListener('click', () => {
            delete item.invisible_role_ids;
            saveGridToProfile();
            renderGrid();
            document.body.removeChild(modalOverlay);
        });

        modalBox.querySelector('#btn-modal-save').addEventListener('click', () => {
            const selected = [];
            checkContainer.querySelectorAll('input[type="checkbox"]:checked').forEach(c => {
                selected.push(parseInt(c.value, 10));
            });
            item.invisible_role_ids = selected;
            saveGridToProfile();
            renderGrid();
            document.body.removeChild(modalOverlay);
        });

        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                document.body.removeChild(modalOverlay);
            }
        });

        modalOverlay.appendChild(modalBox);
        document.body.appendChild(modalOverlay);
    }

    function saveGridToProfile() {
        const activeDomain = TenantProfileManager.getActiveDomain();
        if (activeDomain) {
            const profiles = TenantProfileManager.getProfiles();
            if (profiles[activeDomain]) {
                if (!profiles[activeDomain].inputs) profiles[activeDomain].inputs = {};
                profiles[activeDomain].inputs['create_fields_grid'] = JSON.stringify(gridRows);
            }
        }
        try {
            localStorage.setItem('saved_state_create_fields_grid', JSON.stringify(gridRows));
        } catch (_) { }
    }

    function loadGridFromProfile() {
        const activeDomain = TenantProfileManager.getActiveDomain();
        let loaded = null;
        if (activeDomain) {
            const profiles = TenantProfileManager.getProfiles();
            if (profiles[activeDomain] && profiles[activeDomain].inputs && profiles[activeDomain].inputs['create_fields_grid']) {
                try {
                    loaded = JSON.parse(profiles[activeDomain].inputs['create_fields_grid']);
                } catch (_) { }
            }
        }
        if (!loaded) {
            try {
                const raw = localStorage.getItem('saved_state_create_fields_grid');
                if (raw) loaded = JSON.parse(raw);
            } catch (_) { }
        }
        gridRows = Array.isArray(loaded) ? loaded : [];
        renderGrid();
    }

    function renderGrid() {
        if (!fieldGridTbody) return;
        fieldGridTbody.innerHTML = '';

        if (gridRows.length === 0) {
            if (gridEmptyState) gridEmptyState.style.display = 'block';
            if (btnExecuteCreateFields) {
                btnExecuteCreateFields.textContent = 'Create Custom Fields (0 Fields)';
                btnExecuteCreateFields.disabled = true;
            }
            return;
        }

        if (gridEmptyState) gridEmptyState.style.display = 'none';
        if (btnExecuteCreateFields) {
            btnExecuteCreateFields.textContent = `Create Custom Fields (${gridRows.length} Field${gridRows.length > 1 ? 's' : ''})`;
            btnExecuteCreateFields.disabled = false;
        }

        gridRows.forEach((item, idx) => {
            const tr = document.createElement('tr');
            tr.dataset.index = idx;

            // 1. Index
            const tdIdx = document.createElement('td');
            tdIdx.style.textAlign = 'center';
            tdIdx.style.color = '#64748b';
            tdIdx.textContent = idx + 1;
            tr.appendChild(tdIdx);

            // 2. Title
            const tdTitle = document.createElement('td');
            const inputTitle = document.createElement('input');
            inputTitle.type = 'text';
            inputTitle.className = 'grid-input';
            inputTitle.placeholder = 'e.g. Issue Summary';
            inputTitle.value = item.title || '';
            inputTitle.addEventListener('input', () => {
                item.title = inputTitle.value;
                saveGridToProfile();
            });
            tdTitle.appendChild(inputTitle);
            tr.appendChild(tdTitle);

            // 3. Type
            const tdType = document.createElement('td');
            const selectType = document.createElement('select');
            const optText = document.createElement('option');
            optText.value = 'text';
            optText.textContent = 'Text (单行)';
            const optDate = document.createElement('option');
            optDate.value = 'date';
            optDate.textContent = 'Date (日期)';
            const optDrop = document.createElement('option');
            optDrop.value = 'drop_list';
            optDrop.textContent = 'Dropdown (下拉)';
            selectType.appendChild(optText);
            selectType.appendChild(optDate);
            selectType.appendChild(optDrop);
            selectType.value = item.type || 'text';

            tdType.appendChild(selectType);
            tr.appendChild(tdType);

            // 4. Options
            const tdOpts = document.createElement('td');
            const inputOpts = document.createElement('input');
            inputOpts.type = 'text';
            inputOpts.className = 'grid-input';
            inputOpts.placeholder = 'Option1, Option2, Option3...';
            inputOpts.value = Array.isArray(item.options) ? item.options.join(', ') : (item.options || '');
            inputOpts.disabled = (selectType.value !== 'drop_list');

            selectType.addEventListener('change', () => {
                item.type = selectType.value;
                inputOpts.disabled = (selectType.value !== 'drop_list');
                saveGridToProfile();
            });

            inputOpts.addEventListener('input', () => {
                const raw = inputOpts.value;
                item.options = raw.split(/[,，]/).map(s => s.trim()).filter(Boolean);
                saveGridToProfile();
            });

            tdOpts.appendChild(inputOpts);
            tr.appendChild(tdOpts);

            // 5. Description
            const tdDesc = document.createElement('td');
            const inputDesc = document.createElement('input');
            inputDesc.type = 'text';
            inputDesc.className = 'grid-input';
            inputDesc.placeholder = 'Optional comment...';
            inputDesc.value = item.description || '';
            inputDesc.addEventListener('input', () => {
                item.description = inputDesc.value;
                saveGridToProfile();
            });
            tdDesc.appendChild(inputDesc);
            tr.appendChild(tdDesc);

            // 6. Persona
            const tdPersona = document.createElement('td');
            const inputPersona = document.createElement('input');
            inputPersona.type = 'text';
            inputPersona.className = 'grid-input';
            inputPersona.placeholder = 'All';
            inputPersona.value = item.persona || 'All';
            inputPersona.addEventListener('input', () => {
                item.persona = inputPersona.value.trim() || 'All';
                saveGridToProfile();
                renderRowHiddenBadges(tdHidden, item);
            });
            tdPersona.appendChild(inputPersona);
            tr.appendChild(tdPersona);

            // 7. Hidden Roles
            const tdHidden = document.createElement('td');
            renderRowHiddenBadges(tdHidden, item);
            tr.appendChild(tdHidden);

            // 8. Status
            const tdStatus = document.createElement('td');
            tdStatus.style.textAlign = 'center';
            const badge = document.createElement('span');
            badge.className = `badge-status badge-${item.status || 'ready'}`;
            badge.textContent = item.status === 'success' ? '✓ Created' :
                item.status === 'failed' ? '✕ Failed' :
                    item.status === 'creating' ? 'Creating...' : 'Ready';
            badge.id = `grid-status-${idx}`;
            tdStatus.appendChild(badge);
            tr.appendChild(tdStatus);

            // 9. Action
            const tdAction = document.createElement('td');
            tdAction.style.textAlign = 'center';
            const btnDel = document.createElement('button');
            btnDel.type = 'button';
            btnDel.className = 'btn-row-delete';
            btnDel.textContent = '✕';
            btnDel.title = 'Remove row';
            btnDel.addEventListener('click', () => {
                gridRows.splice(idx, 1);
                renderGrid();
                saveGridToProfile();
            });
            tdAction.appendChild(btnDel);
            tr.appendChild(tdAction);

            fieldGridTbody.appendChild(tr);
        });
    }

    function addRow(title = '', type = 'text', options = [], description = '', persona = 'All') {
        gridRows.push({
            title: title,
            type: type,
            options: options,
            description: description,
            persona: persona,
            status: 'ready'
        });
        renderGrid();
        saveGridToProfile();
    }

    if (btnAddGridRow) {
        btnAddGridRow.addEventListener('click', () => {
            addRow();
        });
    }

    if (btnClearGrid) {
        btnClearGrid.addEventListener('click', () => {
            if (gridRows.length === 0) return;
            if (confirm('Clear all fields from the table?')) {
                gridRows = [];
                renderGrid();
                saveGridToProfile();
                logToConsole('Cleared custom fields table.', 'system');
            }
        });
    }

    if (btnDownloadSampleExcel) {
        btnDownloadSampleExcel.addEventListener('click', () => {
            logToConsole('Downloading custom_fields_template.xlsx...', 'system');
        });
    }

    // Mode Switcher: Upload Excel vs Quick Paste
    if (btnModeUpload && btnModePaste) {
        btnModeUpload.addEventListener('click', () => {
            btnModeUpload.classList.add('active');
            btnModePaste.classList.remove('active');
            if (panelModeUpload) panelModeUpload.style.display = 'block';
            if (panelModePaste) panelModePaste.style.display = 'none';
        });

        btnModePaste.addEventListener('click', () => {
            btnModePaste.classList.add('active');
            btnModeUpload.classList.remove('active');
            if (panelModePaste) {
                panelModePaste.style.display = 'block';
                if (fieldsPasteTextarea) fieldsPasteTextarea.focus();
            }
            if (panelModeUpload) panelModeUpload.style.display = 'none';
        });
    }

    // Smart Multi-line Paste Parser (Supports 3-col simple, 4-col smart, and 5-col extended)
    function parsePastedFieldsText(rawText) {
        if (!rawText || !rawText.trim()) return [];

        const lines = rawText.split(/\r?\n/);
        const parsed = [];
        const knownPersonas = ['agent', 'distributor', 'internal', 'all', '客服', '坐席', '分销商', '分销', '经销商', '全部'];

        lines.forEach((line) => {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('#')) return;

            let cols = [];
            if (line.includes('\t')) {
                // Excel clipboard copy-paste is tab-separated
                cols = line.split('\t').map(c => c.trim());
            } else if (line.includes(';') || line.includes(',')) {
                // Semicolon or comma separated
                cols = line.split(/[;,]/).map(c => c.trim());
            } else {
                // Multi-space separated fallback (2+ spaces)
                cols = line.split(/\s{2,}/).map(c => c.trim());
                if (cols.length < 2) {
                    cols = line.split(/\s+/).map(c => c.trim());
                }
            }

            if (cols.length === 0 || !cols[0]) return;

            const name = cols[0];
            // Skip header rows if present
            const lowerName = name.toLowerCase();
            const lowerCol1 = cols[1] ? cols[1].toLowerCase() : '';
            if (
                lowerName.includes('field') || lowerName.includes('字段') ||
                lowerName === 'name' || lowerName === '名称' ||
                lowerCol1.includes('type') || lowerCol1.includes('类型')
            ) {
                return;
            }

            // Normalize field type
            let fieldType = 'text';
            const rawType = cols[1] ? cols[1].toLowerCase() : '';
            if (rawType.includes('date') || rawType.includes('日期') || rawType.includes('时间') || rawType.includes('time')) {
                fieldType = 'date';
            } else if (
                rawType.includes('drop') || rawType.includes('select') || rawType.includes('list') ||
                rawType.includes('下拉') || rawType.includes('选项')
            ) {
                fieldType = 'drop_list';
            } else {
                fieldType = 'text';
            }

            // Extract options, description, and persona
            let options = [];
            let description = '';
            let persona = 'All';

            if (fieldType === 'drop_list') {
                if (cols.length >= 5) {
                    // Col 0: Name, Col 1: Type, Col 2: Options, Col 3: Description, Col 4: Persona
                    options = cols[2].split(/[,，]/).map(o => o.trim()).filter(Boolean);
                    description = cols[3] || '';
                    persona = cols[4] || 'All';
                } else if (cols.length === 4) {
                    options = cols[2].split(/[,，]/).map(o => o.trim()).filter(Boolean);
                    if (knownPersonas.includes((cols[3] || '').toLowerCase())) {
                        persona = cols[3] || 'All';
                    } else {
                        description = cols[3] || '';
                    }
                } else if (cols.length === 3) {
                    options = cols[2].split(/[,，]/).map(o => o.trim()).filter(Boolean);
                }
            } else {
                // Text or Date
                if (cols.length >= 5) {
                    description = cols[3] || '';
                    persona = cols[4] || 'All';
                } else if (cols.length === 4) {
                    if (knownPersonas.includes((cols[3] || '').toLowerCase())) {
                        persona = cols[3] || 'All';
                        description = cols[2] || '';
                    } else {
                        description = cols[3] || cols[2] || '';
                    }
                } else if (cols.length === 3) {
                    if (knownPersonas.includes((cols[2] || '').toLowerCase())) {
                        persona = cols[2] || 'All';
                    } else {
                        description = cols[2] || '';
                    }
                }
            }

            parsed.push({
                title: name,
                type: fieldType,
                options: options,
                description: description,
                persona: persona,
                status: 'ready'
            });
        });

        return parsed;
    }

    // Quick Paste Actions
    if (btnParsePaste) {
        btnParsePaste.addEventListener('click', () => {
            const rawText = fieldsPasteTextarea ? fieldsPasteTextarea.value : '';
            if (!rawText.trim()) {
                logToConsole('Please paste some field definitions into the text area first.', 'warn');
                return;
            }

            const newFields = parsePastedFieldsText(rawText);
            if (newFields.length === 0) {
                logToConsole('No valid field rows could be detected. Please check format (e.g. Field Name [Tab] Type [Tab] Options [Tab] Description [Tab] Persona).', 'error');
                return;
            }

            // Always append to existing table
            newFields.forEach(f => gridRows.push(f));
            renderGrid();
            saveGridToProfile();

            if (fieldsPasteTextarea) fieldsPasteTextarea.value = '';
            logToConsole(`Successfully parsed and appended ${newFields.length} field(s) to the table grid.`, 'success');
        });
    }

    if (btnPasteSample) {
        btnPasteSample.addEventListener('click', () => {
            if (!fieldsPasteTextarea) return;
            const sampleText = [
                'Customer Name\ttext',
                'Purchase Date\tdate',
                'Product Model\tdrop_list\tModel Alpha, Model Beta, Model Pro',
                'Distributor Feedback\ttext\t\tDealer service evaluation note\tDistributor',
                'Issue Category\tdrop_list\tEngine, Electrical, Body, Maintenance\tPrimary breakdown classification\tAll'
            ].join('\n');
            fieldsPasteTextarea.value = sampleText;
            fieldsPasteTextarea.focus();
            logToConsole('Inserted sample custom fields demonstration with descriptions and personas into paste box.', 'system');
        });
    }

    if (btnPasteClear) {
        btnPasteClear.addEventListener('click', () => {
            if (fieldsPasteTextarea) {
                fieldsPasteTextarea.value = '';
                fieldsPasteTextarea.focus();
            }
        });
    }

    async function handleFileSelected(file) {
        if (!file) return;
        logToConsole(`Processing file: ${file.name}...`, 'system');

        // Try client-side SheetJS first if available
        if (window.XLSX && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
            try {
                const arrayBuffer = await file.arrayBuffer();
                const workbook = window.XLSX.read(arrayBuffer, { type: 'array' });
                const firstSheetName = workbook.SheetNames[0];
                const sheet = workbook.Sheets[firstSheetName];
                const rows = window.XLSX.utils.sheet_to_json(sheet, { header: 1 });

                let parsedCount = 0;
                const knownPersonas = ['agent', 'distributor', 'internal', 'all', '客服', '坐席', '分销商', '分销', '经销商', '全部'];

                rows.forEach((row, idx) => {
                    if (!row || row.length === 0) return;
                    const val0 = String(row[0] || '').trim();
                    if (!val0) return;
                    // Skip header
                    if (idx === 0 && (val0.includes('字段') || val0.toLowerCase().includes('field'))) return;

                    const val1 = String(row[1] || '').trim().toLowerCase();
                    let ftype = 'text';
                    if (val1.includes('drop') || val1.includes('select') || val1.includes('下拉')) {
                        ftype = 'drop_list';
                    } else if (val1.includes('date') || val1.includes('日期')) {
                        ftype = 'date';
                    }

                    const opts = [];
                    let description = '';
                    let persona = 'All';

                    if (ftype === 'drop_list') {
                        if (row.length >= 5) {
                            const rawOpts = String(row[2] || '').trim();
                            if (rawOpts) opts.push(...rawOpts.replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean));
                            description = String(row[3] || '').trim();
                            persona = String(row[4] || 'All').trim() || 'All';
                        } else if (row.length === 4) {
                            const rawOpts = String(row[2] || '').trim();
                            if (rawOpts) opts.push(...rawOpts.replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean));
                            const col3 = String(row[3] || '').trim();
                            if (knownPersonas.includes(col3.toLowerCase())) {
                                persona = col3 || 'All';
                            } else {
                                description = col3;
                            }
                        } else if (row.length === 3) {
                            const rawOpts = String(row[2] || '').trim();
                            if (rawOpts) opts.push(...rawOpts.replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean));
                        }
                    } else {
                        if (row.length >= 5) {
                            description = String(row[3] || '').trim();
                            persona = String(row[4] || 'All').trim() || 'All';
                        } else if (row.length === 4) {
                            const col3 = String(row[3] || '').trim();
                            if (knownPersonas.includes(col3.toLowerCase())) {
                                persona = col3 || 'All';
                                description = String(row[2] || '').trim();
                            } else {
                                description = col3 || String(row[2] || '').trim();
                            }
                        } else if (row.length === 3) {
                            const col2 = String(row[2] || '').trim();
                            if (knownPersonas.includes(col2.toLowerCase())) {
                                persona = col2 || 'All';
                            } else {
                                description = col2;
                            }
                        }
                    }

                    gridRows.push({
                        title: val0,
                        type: ftype,
                        options: opts,
                        description: description,
                        persona: persona,
                        status: 'ready'
                    });
                    parsedCount++;
                });

                renderGrid();
                saveGridToProfile();
                logToConsole(`Successfully parsed ${parsedCount} custom fields from ${file.name}.`, 'success');
                return;
            } catch (err) {
                console.warn('Client-side XLSX parse failed, falling back to server API:', err);
            }
        }

        // Server-side fallback parser via /api/parse-custom-fields-file
        try {
            const reader = new FileReader();
            reader.onload = async (e) => {
                const base64Data = e.target.result.split(',')[1];
                const res = await fetch('/api/parse-custom-fields-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: file.name,
                        content_base64: base64Data
                    })
                });
                const data = await res.json();
                if (data.success && Array.isArray(data.fields)) {
                    data.fields.forEach(f => {
                        gridRows.push({
                            title: f.title,
                            type: f.type,
                            options: f.options || [],
                            description: f.description || '',
                            persona: f.persona || 'All',
                            status: 'ready'
                        });
                    });
                    renderGrid();
                    saveGridToProfile();
                    logToConsole(data.message || `Loaded ${data.fields.length} fields from file.`, 'success');
                } else {
                    logToConsole(`Failed to parse file: ${data.message}`, 'error');
                }
            };
            reader.readAsDataURL(file);
        } catch (err) {
            logToConsole(`Error reading file: ${err.message}`, 'error');
        }
    }

    if (fileFieldsInput) {
        fileFieldsInput.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        fileFieldsInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleFileSelected(e.target.files[0]);
                fileFieldsInput.value = '';
            }
        });
    }

    if (btnBrowseExcel && fileFieldsInput) {
        btnBrowseExcel.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileFieldsInput.click();
        });
    }

    if (btnToolbarBrowse && fileFieldsInput) {
        btnToolbarBrowse.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileFieldsInput.click();
        });
    }

    if (excelDropZone) {
        excelDropZone.addEventListener('click', (e) => {
            if (e.target && (e.target.id === 'btn-browse-excel' || e.target.closest('#btn-browse-excel') || e.target === fileFieldsInput)) {
                return;
            }
            if (fileFieldsInput) fileFieldsInput.click();
        });
        excelDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            excelDropZone.classList.add('drag-over');
        });
        excelDropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            excelDropZone.classList.remove('drag-over');
        });
        excelDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            excelDropZone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFileSelected(e.dataTransfer.files[0]);
            }
        });
    }

    // Execute batch creation
    if (btnExecuteCreateFields) {
        btnExecuteCreateFields.addEventListener('click', async () => {
            const authScript = document.getElementById('global-auth-script').value.trim();
            if (!authScript) {
                logToConsole('Error: Please provide your Global Authentication Script first.', 'error');
                return;
            }

            const validFields = gridRows.filter(r => r.title && r.title.trim());
            if (validFields.length === 0) {
                logToConsole('Error: No valid fields to create. Please enter at least one field name.', 'error');
                return;
            }

            btnExecuteCreateFields.disabled = true;
            btnExecuteCreateFields.textContent = `Creating Fields (0/${validFields.length})...`;
            logToConsole(`Initiating creation of ${validFields.length} custom fields...`, 'system');

            // Reset badges to ready
            validFields.forEach((item, i) => {
                item.status = 'ready';
                const badge = document.getElementById(`grid-status-${i}`);
                if (badge) {
                    badge.className = 'badge-status badge-ready';
                    badge.textContent = 'Ready';
                }
            });

            try {
                const response = await fetch('/api/create-custom-fields', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        auth_script: authScript,
                        fields: validFields.map(f => {
                            const invIds = getEffectiveInvisibleRoleIds(f);
                            return {
                                title: f.title.trim(),
                                type: f.type,
                                options: Array.isArray(f.options) ? f.options : (f.options ? f.options.split(/[,，]/).map(s => s.trim()).filter(Boolean) : []),
                                description: f.description || '',
                                persona: f.persona || 'All',
                                invisible_role_ids: invIds
                            };
                        }),
                        roles: fieldTenantRoles
                    })
                });

                if (!response.ok) {
                    const text = await response.text();
                    try {
                        const errJson = JSON.parse(text);
                        logToConsole(`Creation failed: ${errJson.message}`, 'error');
                    } catch {
                        logToConsole(`Creation failed: ${text}`, 'error');
                    }
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.status === 'progress') {
                                const idx = data.index;
                                if (validFields[idx]) {
                                    validFields[idx].status = data.success ? 'success' : 'failed';
                                }
                                const badge = document.getElementById(`grid-status-${idx}`);
                                if (badge) {
                                    badge.className = `badge-status badge-${data.success ? 'success' : 'failed'}`;
                                    badge.textContent = data.success ? '✓ Created' : '✕ Failed';
                                }
                                btnExecuteCreateFields.textContent = `Creating Fields (${idx + 1}/${validFields.length})...`;
                                logToConsole(data.message, data.success ? 'success' : 'error');
                            } else if (data.status === 'log') {
                                logToConsole(data.message, 'success');
                            } else if (data.status === 'warn') {
                                logToConsole(data.message, 'warn');
                            } else if (data.status === 'done') {
                                logToConsole(data.message, 'success');
                            } else if (data.status === 'error') {
                                logToConsole(`Error: ${data.message}`, 'error');
                            } else {
                                logToConsole(data.message, 'system');
                            }
                        } catch (e) {
                            logToConsole(line, 'system');
                        }
                    }
                }
                saveGridToProfile();
            } catch (err) {
                logToConsole(`Batch creation failed: ${err.message}`, 'error');
            } finally {
                btnExecuteCreateFields.disabled = false;
                btnExecuteCreateFields.textContent = `Create Custom Fields (${gridRows.length} Fields)`;
            }
        });
    }

    // Initialize grid and persona rules on load
    loadGridFromProfile();
    loadPersonaRulesFromProfile();

    // ==========================================================================
    // Customers Module: Fetch Customer Custom Fields Logic
    // ==========================================================================
    const btnFetchCustomerFields = document.getElementById('btn-fetch-customer-fields');
    const fFetchedCustomerJson = document.getElementById('f-fetched-customer-json');
    const fetchCustomerFieldsStats = document.getElementById('fetch-customer-fields-stats');
    const btnCopyFetchedCustomerFields = document.getElementById('btn-copy-fetched-customer-fields');
    const btnDownloadFetchedCustomerFields = document.getElementById('btn-download-fetched-customer-fields');

    function renderCustomerFieldStats(count, stats) {
        if (!fetchCustomerFieldsStats) return;
        fetchCustomerFieldsStats.innerHTML = '';
        if (count === undefined || count === null) {
            fetchCustomerFieldsStats.style.display = 'none';
            return;
        }

        fetchCustomerFieldsStats.style.display = 'flex';
        const totalChip = document.createElement('span');
        totalChip.className = 'stat-chip stat-total';
        totalChip.textContent = `Total: ${count}`;
        fetchCustomerFieldsStats.appendChild(totalChip);

        if (stats && typeof stats === 'object') {
            Object.entries(stats).forEach(([type, cnt]) => {
                const chip = document.createElement('span');
                chip.className = 'stat-chip';
                chip.textContent = `${type}: ${cnt}`;
                fetchCustomerFieldsStats.appendChild(chip);
            });
        }
    }

    if (btnFetchCustomerFields) {
        btnFetchCustomerFields.addEventListener('click', async () => {
            const authScript = document.getElementById('global-auth-script').value.trim();
            if (!authScript) {
                logToConsole('Error: Please paste your Global Authentication Script first.', 'error');
                return;
            }

            btnFetchCustomerFields.disabled = true;
            btnFetchCustomerFields.textContent = 'Fetching Customer Fields...';
            logToConsole('Fetching customer custom fields from Web Admin API...', 'system');

            try {
                const res = await fetch('/api/fetch-customer-fields', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ auth_script: authScript })
                });

                const result = await res.json();
                if (result.success) {
                    if (fFetchedCustomerJson) {
                        fFetchedCustomerJson.value = JSON.stringify(result.fields_json, null, 2);
                        fFetchedCustomerJson.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    renderCustomerFieldStats(result.count, result.stats);
                    logToConsole(result.message, 'success');
                } else {
                    logToConsole(`Error: ${result.message}`, 'error');
                }
            } catch (err) {
                logToConsole(`Failed fetching customer custom fields: ${err.message}`, 'error');
            } finally {
                btnFetchCustomerFields.disabled = false;
                btnFetchCustomerFields.textContent = 'Fetch Current Customer Fields from Tenant';
            }
        });
    }

    if (btnCopyFetchedCustomerFields && fFetchedCustomerJson) {
        btnCopyFetchedCustomerFields.addEventListener('click', async () => {
            const text = fFetchedCustomerJson.value.trim();
            if (!text) {
                logToConsole('No JSON to copy. Please fetch customer custom fields first.', 'warn');
                return;
            }
            try {
                await navigator.clipboard.writeText(text);
                logToConsole('Customer custom fields JSON copied to clipboard.', 'success');
            } catch {
                fFetchedCustomerJson.select();
                document.execCommand('copy');
                logToConsole('Customer custom fields JSON copied to clipboard.', 'success');
            }
        });
    }

    if (btnDownloadFetchedCustomerFields && fFetchedCustomerJson) {
        btnDownloadFetchedCustomerFields.addEventListener('click', () => {
            const text = fFetchedCustomerJson.value.trim();
            if (!text) {
                logToConsole('No JSON to download. Please fetch customer custom fields first.', 'warn');
                return;
            }
            const blob = new Blob([text], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'customer_fields.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            logToConsole('Downloading customer_fields.json...', 'system');
        });
    }

    // ==========================================================================
    // Customers Module: Create Customer Custom Fields (Dual Mode: Excel / Paste / Grid)
    // ==========================================================================
    const btnModeCustomerUpload = document.getElementById('btn-mode-customer-upload');
    const btnModeCustomerPaste = document.getElementById('btn-mode-customer-paste');
    const panelModeCustomerUpload = document.getElementById('panel-mode-customer-upload');
    const panelModeCustomerPaste = document.getElementById('panel-mode-customer-paste');

    const customerFieldsPasteTextarea = document.getElementById('customer-fields-paste-textarea');
    const btnPasteCustomerSample = document.getElementById('btn-paste-customer-sample');
    const btnPasteCustomerClear = document.getElementById('btn-paste-customer-clear');
    const btnParseCustomerPaste = document.getElementById('btn-parse-customer-paste');

    const fileCustomerFieldsInput = document.getElementById('file-customer-fields-input');
    const excelCustomerDropZone = document.getElementById('excel-customer-drop-zone');
    const btnBrowseCustomerExcel = document.getElementById('btn-browse-customer-excel');
    const btnToolbarCustomerBrowse = document.getElementById('btn-toolbar-customer-browse');
    const btnDownloadSampleCustomerExcel = document.getElementById('btn-download-sample-customer-excel');
    const btnAddCustomerGridRow = document.getElementById('btn-add-customer-grid-row');
    const btnClearCustomerGrid = document.getElementById('btn-clear-customer-grid');
    const customerFieldGridTbody = document.getElementById('customer-field-grid-tbody');
    const customerGridEmptyState = document.getElementById('customer-grid-empty-state');
    const btnExecuteCreateCustomerFields = document.getElementById('btn-execute-create-customer-fields');

    let customerGridRows = [];

    function saveCustomerGridToProfile() {
        const activeDomain = TenantProfileManager.getActiveDomain();
        if (activeDomain) {
            const profiles = TenantProfileManager.getProfiles();
            if (profiles[activeDomain]) {
                if (!profiles[activeDomain].inputs) profiles[activeDomain].inputs = {};
                profiles[activeDomain].inputs['create_customer_fields_grid'] = JSON.stringify(customerGridRows);
            }
        }
        try {
            localStorage.setItem('saved_state_create_customer_fields_grid', JSON.stringify(customerGridRows));
        } catch (_) { }
    }

    function loadCustomerGridFromProfile() {
        const activeDomain = TenantProfileManager.getActiveDomain();
        let loaded = null;
        if (activeDomain) {
            const profiles = TenantProfileManager.getProfiles();
            if (profiles[activeDomain] && profiles[activeDomain].inputs && profiles[activeDomain].inputs['create_customer_fields_grid']) {
                try {
                    loaded = JSON.parse(profiles[activeDomain].inputs['create_customer_fields_grid']);
                } catch (_) { }
            }
        }
        if (!loaded) {
            try {
                const raw = localStorage.getItem('saved_state_create_customer_fields_grid');
                if (raw) loaded = JSON.parse(raw);
            } catch (_) { }
        }
        customerGridRows = Array.isArray(loaded) ? loaded : [];
        renderCustomerGrid();
    }

    function renderCustomerGrid() {
        if (!customerFieldGridTbody) return;
        customerFieldGridTbody.innerHTML = '';

        if (customerGridRows.length === 0) {
            if (customerGridEmptyState) customerGridEmptyState.style.display = 'block';
            if (btnExecuteCreateCustomerFields) {
                btnExecuteCreateCustomerFields.textContent = 'Create Customer Fields (0 Fields)';
                btnExecuteCreateCustomerFields.disabled = true;
            }
            return;
        }

        if (customerGridEmptyState) customerGridEmptyState.style.display = 'none';
        if (btnExecuteCreateCustomerFields) {
            btnExecuteCreateCustomerFields.textContent = `Create Customer Fields (${customerGridRows.length} Field${customerGridRows.length > 1 ? 's' : ''})`;
            btnExecuteCreateCustomerFields.disabled = false;
        }

        customerGridRows.forEach((item, idx) => {
            const tr = document.createElement('tr');
            tr.dataset.index = idx;

            // 1. Index
            const tdIdx = document.createElement('td');
            tdIdx.style.textAlign = 'center';
            tdIdx.style.color = '#64748b';
            tdIdx.textContent = idx + 1;
            tr.appendChild(tdIdx);

            // 2. Title
            const tdTitle = document.createElement('td');
            const inputTitle = document.createElement('input');
            inputTitle.type = 'text';
            inputTitle.className = 'grid-input';
            inputTitle.placeholder = 'e.g. Customer Address';
            inputTitle.value = item.title || '';
            inputTitle.addEventListener('input', () => {
                item.title = inputTitle.value;
                saveCustomerGridToProfile();
            });
            tdTitle.appendChild(inputTitle);
            tr.appendChild(tdTitle);

            // 3. Type
            const tdType = document.createElement('td');
            const selectType = document.createElement('select');
            const optText = document.createElement('option');
            optText.value = 'text';
            optText.textContent = 'Text (单行)';
            const optDate = document.createElement('option');
            optDate.value = 'date';
            optDate.textContent = 'Date (日期)';
            const optDrop = document.createElement('option');
            optDrop.value = 'drop_list';
            optDrop.textContent = 'Dropdown (下拉)';
            selectType.appendChild(optText);
            selectType.appendChild(optDate);
            selectType.appendChild(optDrop);
            selectType.value = item.type || 'text';

            tdType.appendChild(selectType);
            tr.appendChild(tdType);

            // 4. Options
            const tdOpts = document.createElement('td');
            const inputOpts = document.createElement('input');
            inputOpts.type = 'text';
            inputOpts.className = 'grid-input';
            inputOpts.placeholder = 'Option1, Option2, Option3...';
            inputOpts.value = Array.isArray(item.options) ? item.options.join(', ') : (item.options || '');
            inputOpts.disabled = (selectType.value !== 'drop_list');

            selectType.addEventListener('change', () => {
                item.type = selectType.value;
                inputOpts.disabled = (selectType.value !== 'drop_list');
                saveCustomerGridToProfile();
            });

            inputOpts.addEventListener('input', () => {
                const raw = inputOpts.value;
                item.options = raw.split(/[,，]/).map(s => s.trim()).filter(Boolean);
                saveCustomerGridToProfile();
            });

            tdOpts.appendChild(inputOpts);
            tr.appendChild(tdOpts);

            // 5. Description
            const tdDesc = document.createElement('td');
            const inputDesc = document.createElement('input');
            inputDesc.type = 'text';
            inputDesc.className = 'grid-input';
            inputDesc.placeholder = 'Optional comment...';
            inputDesc.value = item.description || '';
            inputDesc.addEventListener('input', () => {
                item.description = inputDesc.value;
                saveCustomerGridToProfile();
            });
            tdDesc.appendChild(inputDesc);
            tr.appendChild(tdDesc);

            // 6. Status
            const tdStatus = document.createElement('td');
            tdStatus.style.textAlign = 'center';
            const badge = document.createElement('span');
            badge.className = `badge-status badge-${item.status || 'ready'}`;
            badge.textContent = item.status === 'success' ? '✓ Created' :
                item.status === 'failed' ? '✕ Failed' :
                    item.status === 'creating' ? 'Creating...' : 'Ready';
            badge.id = `customer-grid-status-${idx}`;
            tdStatus.appendChild(badge);
            tr.appendChild(tdStatus);

            // 7. Action
            const tdAction = document.createElement('td');
            tdAction.style.textAlign = 'center';
            const btnDel = document.createElement('button');
            btnDel.type = 'button';
            btnDel.className = 'btn-del-row';
            btnDel.textContent = '✕';
            btnDel.title = 'Delete field row';
            btnDel.addEventListener('click', () => {
                customerGridRows.splice(idx, 1);
                renderCustomerGrid();
                saveCustomerGridToProfile();
            });
            tdAction.appendChild(btnDel);
            tr.appendChild(tdAction);

            customerFieldGridTbody.appendChild(tr);
        });
    }

    function addCustomerRow(title = '', type = 'text', options = [], description = '') {
        customerGridRows.push({
            title: title,
            type: type,
            options: options,
            description: description,
            status: 'ready'
        });
        renderCustomerGrid();
        saveCustomerGridToProfile();
    }

    if (btnAddCustomerGridRow) {
        btnAddCustomerGridRow.addEventListener('click', () => {
            addCustomerRow();
        });
    }

    if (btnClearCustomerGrid) {
        btnClearCustomerGrid.addEventListener('click', () => {
            if (customerGridRows.length === 0) return;
            if (confirm('Clear all customer fields from the table?')) {
                customerGridRows = [];
                renderCustomerGrid();
                saveCustomerGridToProfile();
                logToConsole('Cleared customer fields table.', 'system');
            }
        });
    }

    if (btnDownloadSampleCustomerExcel) {
        btnDownloadSampleCustomerExcel.addEventListener('click', () => {
            logToConsole('Downloading custom_fields_template.xlsx...', 'system');
        });
    }

    // Customer Mode Switcher: Upload Excel vs Quick Paste
    if (btnModeCustomerUpload && btnModeCustomerPaste) {
        btnModeCustomerUpload.addEventListener('click', () => {
            btnModeCustomerUpload.classList.add('active');
            btnModeCustomerPaste.classList.remove('active');
            if (panelModeCustomerUpload) panelModeCustomerUpload.style.display = 'block';
            if (panelModeCustomerPaste) panelModeCustomerPaste.style.display = 'none';
        });

        btnModeCustomerPaste.addEventListener('click', () => {
            btnModeCustomerPaste.classList.add('active');
            btnModeCustomerUpload.classList.remove('active');
            if (panelModeCustomerPaste) {
                panelModeCustomerPaste.style.display = 'block';
                if (customerFieldsPasteTextarea) customerFieldsPasteTextarea.focus();
            }
            if (panelModeCustomerUpload) panelModeCustomerUpload.style.display = 'none';
        });
    }

    // Customer Quick Paste Actions
    if (btnParseCustomerPaste) {
        btnParseCustomerPaste.addEventListener('click', () => {
            const rawText = customerFieldsPasteTextarea ? customerFieldsPasteTextarea.value : '';
            if (!rawText.trim()) {
                logToConsole('Please paste some customer field definitions into the text area first.', 'warn');
                return;
            }

            const newFields = parsePastedFieldsText(rawText);
            if (newFields.length === 0) {
                logToConsole('No valid field rows could be detected. Please check format (e.g. Field Name [Tab] Type [Tab] Options [Tab] Description).', 'error');
                return;
            }

            newFields.forEach(f => customerGridRows.push(f));
            renderCustomerGrid();
            saveCustomerGridToProfile();

            if (customerFieldsPasteTextarea) customerFieldsPasteTextarea.value = '';
            logToConsole(`Successfully parsed and appended ${newFields.length} customer field(s) to the table grid.`, 'success');
        });
    }

    if (btnPasteCustomerSample) {
        btnPasteCustomerSample.addEventListener('click', () => {
            if (!customerFieldsPasteTextarea) return;
            const sampleText = [
                'Customer Address\ttext\t\tPrimary residence location',
                'Birth Date\tdate\t\tCustomer birthday for loyalty campaigns',
                'Preferred Product\tdrop_list\tModel Alpha, Model Beta, Model Pro\tPrimary product of interest',
                'Customer Level\tdrop_list\tVIP, Gold, Silver, Standard\tTier status',
                'VIP Code\ttext\t\tInternal VIP reference'
            ].join('\n');
            customerFieldsPasteTextarea.value = sampleText;
            customerFieldsPasteTextarea.focus();
            logToConsole('Inserted sample customer custom fields into paste box.', 'system');
        });
    }

    if (btnPasteCustomerClear) {
        btnPasteCustomerClear.addEventListener('click', () => {
            if (customerFieldsPasteTextarea) {
                customerFieldsPasteTextarea.value = '';
                customerFieldsPasteTextarea.focus();
            }
        });
    }

    async function handleCustomerFileSelected(file) {
        if (!file) return;
        logToConsole(`Processing customer fields file: ${file.name}...`, 'system');

        // Client-side SheetJS if available
        if (window.XLSX && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
            try {
                const arrayBuffer = await file.arrayBuffer();
                const workbook = window.XLSX.read(arrayBuffer, { type: 'array' });
                const firstSheetName = workbook.SheetNames[0];
                const sheet = workbook.Sheets[firstSheetName];
                const rows = window.XLSX.utils.sheet_to_json(sheet, { header: 1 });

                let parsedCount = 0;
                rows.forEach((row, idx) => {
                    if (!row || row.length === 0) return;
                    const val0 = String(row[0] || '').trim();
                    if (!val0) return;
                    if (idx === 0 && (val0.includes('字段') || val0.toLowerCase().includes('field'))) return;

                    const val1 = String(row[1] || '').trim().toLowerCase();
                    let ftype = 'text';
                    if (val1.includes('drop') || val1.includes('select') || val1.includes('下拉')) {
                        ftype = 'drop_list';
                    } else if (val1.includes('date') || val1.includes('日期')) {
                        ftype = 'date';
                    }

                    const opts = [];
                    let description = '';

                    if (ftype === 'drop_list') {
                        if (row.length >= 4) {
                            const rawOpts = String(row[2] || '').trim();
                            if (rawOpts) opts.push(...rawOpts.replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean));
                            description = String(row[3] || '').trim();
                        } else if (row.length === 3) {
                            const rawOpts = String(row[2] || '').trim();
                            if (rawOpts) opts.push(...rawOpts.replace(/，/g, ',').split(',').map(s => s.trim()).filter(Boolean));
                        }
                    } else {
                        if (row.length >= 4) {
                            description = String(row[3] || row[2] || '').trim();
                        } else if (row.length === 3) {
                            description = String(row[2] || '').trim();
                        }
                    }

                    customerGridRows.push({
                        title: val0,
                        type: ftype,
                        options: opts,
                        description: description,
                        status: 'ready'
                    });
                    parsedCount++;
                });

                renderCustomerGrid();
                saveCustomerGridToProfile();
                logToConsole(`Successfully parsed ${parsedCount} customer custom fields from ${file.name}.`, 'success');
                return;
            } catch (err) {
                console.warn('Client-side XLSX parse failed, falling back to server API:', err);
            }
        }

        // Server-side fallback parser
        try {
            const reader = new FileReader();
            reader.onload = async (e) => {
                const base64Data = e.target.result.split(',')[1];
                const res = await fetch('/api/parse-custom-fields-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: file.name,
                        content_base64: base64Data
                    })
                });
                const data = await res.json();
                if (data.success && Array.isArray(data.fields)) {
                    data.fields.forEach(f => {
                        customerGridRows.push({
                            title: f.title,
                            type: f.type,
                            options: f.options || [],
                            description: f.description || '',
                            status: 'ready'
                        });
                    });
                    renderCustomerGrid();
                    saveCustomerGridToProfile();
                    logToConsole(data.message || `Loaded ${data.fields.length} customer fields from file.`, 'success');
                } else {
                    logToConsole(`Failed to parse file: ${data.message}`, 'error');
                }
            };
            reader.readAsDataURL(file);
        } catch (err) {
            logToConsole(`Error reading file: ${err.message}`, 'error');
        }
    }

    if (fileCustomerFieldsInput) {
        fileCustomerFieldsInput.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        fileCustomerFieldsInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleCustomerFileSelected(e.target.files[0]);
                fileCustomerFieldsInput.value = '';
            }
        });
    }

    if (btnBrowseCustomerExcel && fileCustomerFieldsInput) {
        btnBrowseCustomerExcel.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileCustomerFieldsInput.click();
        });
    }

    if (btnToolbarCustomerBrowse && fileCustomerFieldsInput) {
        btnToolbarCustomerBrowse.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileCustomerFieldsInput.click();
        });
    }

    if (excelCustomerDropZone) {
        excelCustomerDropZone.addEventListener('click', (e) => {
            if (e.target && (e.target.id === 'btn-browse-customer-excel' || e.target.closest('#btn-browse-customer-excel') || e.target === fileCustomerFieldsInput)) {
                return;
            }
            if (fileCustomerFieldsInput) fileCustomerFieldsInput.click();
        });
        excelCustomerDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            excelCustomerDropZone.classList.add('drag-over');
        });
        excelCustomerDropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            excelCustomerDropZone.classList.remove('drag-over');
        });
        excelCustomerDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            excelCustomerDropZone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleCustomerFileSelected(e.dataTransfer.files[0]);
            }
        });
    }

    // Execute Customer batch creation
    if (btnExecuteCreateCustomerFields) {
        btnExecuteCreateCustomerFields.addEventListener('click', async () => {
            const authScript = document.getElementById('global-auth-script').value.trim();
            if (!authScript) {
                logToConsole('Error: Please provide your Global Authentication Script first.', 'error');
                return;
            }

            const validFields = customerGridRows.filter(r => r.title && r.title.trim());
            if (validFields.length === 0) {
                logToConsole('Error: No valid customer fields to create. Please enter at least one field name.', 'error');
                return;
            }

            btnExecuteCreateCustomerFields.disabled = true;
            btnExecuteCreateCustomerFields.textContent = `Creating Customer Fields (0/${validFields.length})...`;
            logToConsole(`Initiating creation of ${validFields.length} customer custom fields...`, 'system');

            validFields.forEach((item, i) => {
                item.status = 'ready';
                const badge = document.getElementById(`customer-grid-status-${i}`);
                if (badge) {
                    badge.className = 'badge-status badge-ready';
                    badge.textContent = 'Ready';
                }
            });

            try {
                const response = await fetch('/api/create-customer-fields', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        auth_script: authScript,
                        fields: validFields.map(f => ({
                            title: f.title.trim(),
                            type: f.type,
                            options: Array.isArray(f.options) ? f.options : (f.options ? f.options.split(/[,，]/).map(s => s.trim()).filter(Boolean) : []),
                            description: f.description || ''
                        }))
                    })
                });

                if (!response.ok) {
                    const text = await response.text();
                    try {
                        const errJson = JSON.parse(text);
                        logToConsole(`Creation failed: ${errJson.message}`, 'error');
                    } catch {
                        logToConsole(`Creation failed: ${text}`, 'error');
                    }
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.status === 'progress') {
                                const idx = data.index;
                                if (validFields[idx]) {
                                    validFields[idx].status = data.success ? 'success' : 'failed';
                                }
                                const badge = document.getElementById(`customer-grid-status-${idx}`);
                                if (badge) {
                                    badge.className = `badge-status badge-${data.success ? 'success' : 'failed'}`;
                                    badge.textContent = data.success ? '✓ Created' : '✕ Failed';
                                }
                                btnExecuteCreateCustomerFields.textContent = `Creating Customer Fields (${idx + 1}/${validFields.length})...`;
                                logToConsole(data.message, data.success ? 'success' : 'error');
                            } else if (data.status === 'done') {
                                logToConsole(data.message, 'success');
                            } else if (data.status === 'error') {
                                logToConsole(`Error: ${data.message}`, 'error');
                            } else {
                                logToConsole(data.message, 'system');
                            }
                        } catch (e) {
                            logToConsole(line, 'system');
                        }
                    }
                }
                saveCustomerGridToProfile();
            } catch (err) {
                logToConsole(`Customer batch creation failed: ${err.message}`, 'error');
            } finally {
                btnExecuteCreateCustomerFields.disabled = false;
                btnExecuteCreateCustomerFields.textContent = `Create Customer Fields (${customerGridRows.length} Fields)`;
            }
        });
    }

    // Initialize customer grid on load
    loadCustomerGridFromProfile();

    // =========================================================================
    // Streamlined Agent Creation (Metadata Auto-Discovery & Batch Actions)
    // =========================================================================
    let agentOverviewRows = [];
    let platformMetadata = { roles: [], groups: [], default_group_id: null, default_dept_id: null };

    const badgeAgentMetadataStatus = document.getElementById('badge-agent-metadata-status');
    const btnRefreshAgentMetadata = document.getElementById('btn-refresh-agent-metadata');
    const agentGlobalProfile = document.getElementById('agent-global-profile');
    const agentGlobalRole = document.getElementById('agent-global-role');
    const agentGlobalPassword = document.getElementById('agent-global-password');

    const btnModeAgentPaste = document.getElementById('btn-mode-agent-paste');
    const btnModeAgentUpload = document.getElementById('btn-mode-agent-upload');
    const panelModeAgentPaste = document.getElementById('panel-mode-agent-paste');
    const panelModeAgentUpload = document.getElementById('panel-mode-agent-upload');

    const agentsPasteTextarea = document.getElementById('agents-paste-textarea');
    const btnPasteAgentSample = document.getElementById('btn-paste-agent-sample');
    const btnPasteAgentClear = document.getElementById('btn-paste-agent-clear');
    const btnLoadAgentList = document.getElementById('btn-load-agent-list');

    const fileAgentsInput = document.getElementById('file-agents-input');
    const excelAgentDropZone = document.getElementById('excel-agent-drop-zone');
    const btnBrowseAgentExcel = document.getElementById('btn-browse-agent-excel');

    const agentSelectAll = document.getElementById('agent-select-all');
    const agentSelectedCount = document.getElementById('agent-selected-count');
    const agentTotalBadge = document.getElementById('agent-total-badge');
    const agentBatchType = document.getElementById('agent-batch-type');
    const btnApplyBatchType = document.getElementById('btn-apply-batch-type');
    const agentBatchRole = document.getElementById('agent-batch-role');
    const btnApplyBatchRole = document.getElementById('btn-apply-batch-role');
    const btnDeleteSelectedAgents = document.getElementById('btn-delete-selected-agents');

    const agentGridTbody = document.getElementById('agent-grid-tbody');
    const agentGridEmptyState = document.getElementById('agent-grid-empty-state');
    const btnExecuteCreateAgents = document.getElementById('btn-execute-create-agents');

    // 1. Fetch Platform Roles, Groups, and Departments automatically
    async function fetchAgentMetadata(silent = false) {
        const authScript = document.getElementById('global-auth-script').value.trim();
        if (!authScript) {
            if (badgeAgentMetadataStatus) {
                badgeAgentMetadataStatus.textContent = 'Paste Auth Script to Load Roles';
                badgeAgentMetadataStatus.className = 'badge-status badge-pending';
            }
            return;
        }

        if (badgeAgentMetadataStatus) {
            badgeAgentMetadataStatus.textContent = 'Fetching Roles & Metadata...';
            badgeAgentMetadataStatus.className = 'badge-status badge-uploading';
        }

        try {
            const resp = await fetch('/api/fetch-agent-metadata', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ auth_script: authScript })
            });

            const result = await resp.json();
            if (result.success && result.data) {
                platformMetadata = result.data;
                const roles = platformMetadata.roles || [];

                // Populate Global Role dropdown & Batch Role dropdown
                populateRoleDropdown(agentGlobalRole, roles);
                populateRoleDropdown(agentBatchRole, roles, 'Select Role...');

                if (badgeAgentMetadataStatus) {
                    badgeAgentMetadataStatus.textContent = `✓ ${roles.length} Roles Loaded`;
                    badgeAgentMetadataStatus.className = 'badge-status badge-success';
                }

                if (!silent) {
                    logToConsole(`Successfully loaded ${roles.length} roles and ${platformMetadata.groups.length} groups from tenant.`, 'success');
                }

                // If overview rows already exist, refresh their role options
                renderAgentOverview();
            } else {
                if (badgeAgentMetadataStatus) {
                    badgeAgentMetadataStatus.textContent = '✕ Metadata Failed';
                    badgeAgentMetadataStatus.className = 'badge-status badge-failed';
                }
                if (!silent) {
                    logToConsole(`Could not fetch roles from tenant: ${result.message}`, 'error');
                }
            }
        } catch (err) {
            if (badgeAgentMetadataStatus) {
                badgeAgentMetadataStatus.textContent = '✕ Network Error';
                badgeAgentMetadataStatus.className = 'badge-status badge-failed';
            }
            if (!silent) {
                logToConsole(`Error fetching roles: ${err.message}`, 'error');
            }
        }
    }

    function populateRoleDropdown(selectEl, roles, placeholder = null) {
        if (!selectEl) return;
        const previousVal = selectEl.value;
        selectEl.innerHTML = '';

        if (placeholder) {
            const defOpt = document.createElement('option');
            defOpt.value = '';
            defOpt.textContent = placeholder;
            selectEl.appendChild(defOpt);
        }

        let defaultRoleId = '';
        roles.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.id;
            opt.textContent = `${r.name} (ID: ${r.id})`;
            selectEl.appendChild(opt);

            // Default to "客服" role if present
            if (r.name.includes('客服') && !defaultRoleId) {
                defaultRoleId = r.id;
            }
        });

        if (previousVal && Array.from(selectEl.options).some(o => o.value == previousVal)) {
            selectEl.value = previousVal;
        } else if (defaultRoleId && !placeholder) {
            selectEl.value = defaultRoleId;
        } else if (roles.length > 0 && !placeholder) {
            selectEl.value = roles[0].id;
        }
    }

    if (btnRefreshAgentMetadata) {
        btnRefreshAgentMetadata.addEventListener('click', () => fetchAgentMetadata(false));
    }

    // Auto-fetch metadata whenever Global Auth Script is pasted or edited
    const globalAuthEl = document.getElementById('global-auth-script');
    if (globalAuthEl) {
        let authDebounce = null;
        globalAuthEl.addEventListener('input', () => {
            clearTimeout(authDebounce);
            authDebounce = setTimeout(() => {
                if (globalAuthEl.value.trim()) {
                    fetchAgentMetadata(true);
                }
            }, 600);
        });
        // Trigger on page load if auth script is already restored from localStorage
        if (globalAuthEl.value.trim()) {
            setTimeout(() => fetchAgentMetadata(true), 300);
        }
    }

    // 2. Mode Switcher (Paste vs Upload)
    if (btnModeAgentPaste && btnModeAgentUpload) {
        btnModeAgentPaste.addEventListener('click', () => {
            btnModeAgentPaste.classList.add('active');
            btnModeAgentUpload.classList.remove('active');
            if (panelModeAgentPaste) panelModeAgentPaste.style.display = 'block';
            if (panelModeAgentUpload) panelModeAgentUpload.style.display = 'none';
            if (agentsPasteTextarea) agentsPasteTextarea.focus();
        });
        btnModeAgentUpload.addEventListener('click', () => {
            btnModeAgentUpload.classList.add('active');
            btnModeAgentPaste.classList.remove('active');
            if (panelModeAgentUpload) panelModeAgentUpload.style.display = 'block';
            if (panelModeAgentPaste) panelModeAgentPaste.style.display = 'none';
        });
    }

    // Sample insertion and clear
    if (btnPasteAgentSample) {
        btnPasteAgentSample.addEventListener('click', () => {
            if (!agentsPasteTextarea) return;
            agentsPasteTextarea.value = [
                'agent1@example.com, Agent One',
                'agent2@example.com, Alex Agent',
                'agent3@example.com\tSam Support',
                'agent4@example.com'
            ].join('\n');
            agentsPasteTextarea.focus();
            logToConsole('Inserted sample agent emails with nicknames into paste box.', 'system');
        });
    }

    if (btnPasteAgentClear) {
        btnPasteAgentClear.addEventListener('click', () => {
            if (agentsPasteTextarea) {
                agentsPasteTextarea.value = '';
                agentsPasteTextarea.focus();
            }
        });
    }

    // 3. Load agents into Overview List
    function parseAgentLine(line) {
        if (!line || !line.trim()) return null;
        const trimmed = line.trim();
        const delimiter = trimmed.includes('\t') ? '\t' : (trimmed.includes(',') ? ',' : null);
        let email = '';
        let nickName = '';
        if (delimiter) {
            const parts = trimmed.split(delimiter).map(p => p.trim());
            email = parts[0];
            nickName = parts[1] || '';
        } else {
            const spaceIdx = trimmed.indexOf(' ');
            if (spaceIdx > 0 && trimmed.slice(0, spaceIdx).includes('@')) {
                email = trimmed.slice(0, spaceIdx).trim();
                nickName = trimmed.slice(spaceIdx + 1).trim();
            } else {
                email = trimmed;
            }
        }
        email = email.toLowerCase();
        if (!email.includes('@')) return null;
        return { email, nick_name: nickName };
    }

    function addAgentsToOverview(itemsList) {
        const defaultProfile = agentGlobalProfile ? agentGlobalProfile.value : 'all';
        const defaultRoleId = agentGlobalRole ? agentGlobalRole.value : '';

        let addedCount = 0;
        itemsList.forEach(raw => {
            let email = '';
            let nickName = '';
            let roleId = defaultRoleId;
            let profile = defaultProfile;

            if (typeof raw === 'object' && raw !== null) {
                email = String(raw.email || '').trim().toLowerCase();
                nickName = String(raw.nick_name || raw.name || '').trim();
                if (raw.role_id) roleId = raw.role_id;
                if (raw.profile) profile = raw.profile;
            } else {
                const parsed = parseAgentLine(String(raw));
                if (!parsed) return;
                email = parsed.email;
                nickName = parsed.nick_name;
            }

            if (!email || !email.includes('@')) return;

            // Avoid duplicate emails in list
            if (agentOverviewRows.some(r => r.email === email)) return;

            agentOverviewRows.push({
                id: 'agent_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
                email: email,
                nick_name: nickName,
                profile: profile,
                role_id: roleId,
                status: 'ready',
                selected: false
            });
            addedCount++;
        });

        renderAgentOverview();
        return addedCount;
    }

    if (btnLoadAgentList) {
        btnLoadAgentList.addEventListener('click', () => {
            const rawText = agentsPasteTextarea ? agentsPasteTextarea.value : '';
            if (!rawText.trim()) {
                logToConsole('Please paste agent email addresses first.', 'warn');
                return;
            }

            const lines = rawText.split('\n');
            const added = addAgentsToOverview(lines);
            if (agentsPasteTextarea) agentsPasteTextarea.value = '';
            logToConsole(`Loaded ${added} agent(s) into overview list.`, 'success');
        });
    }

    // Excel & CSV File Upload
    async function handleAgentFile(file) {
        if (!file) return;
        logToConsole(`Reading agents file: ${file.name}...`, 'system');

        if (window.XLSX && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
            try {
                const arrayBuffer = await file.arrayBuffer();
                const workbook = window.XLSX.read(arrayBuffer, { type: 'array' });
                const sheet = workbook.Sheets[workbook.SheetNames[0]];
                const rows = window.XLSX.utils.sheet_to_json(sheet, { header: 1 });
                const agentItems = [];
                rows.forEach((r, idx) => {
                    if (!r || r.length === 0) return;
                    const val = String(r[0] || '').trim();
                    if (idx === 0 && (val.toLowerCase().includes('email') || val.includes('邮箱'))) return;
                    if (val && val.includes('@')) {
                        const nick = r.length > 1 && r[1] ? String(r[1]).trim() : '';
                        agentItems.push({ email: val, nick_name: nick });
                    }
                });
                const added = addAgentsToOverview(agentItems);
                logToConsole(`Loaded ${added} agent(s) from ${file.name}.`, 'success');
                return;
            } catch (err) {
                console.warn('XLSX client parse failed, using server API:', err);
            }
        }

        try {
            const reader = new FileReader();
            reader.onload = async (e) => {
                const base64Data = e.target.result.split(',')[1];
                const res = await fetch('/api/parse-agents-file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        filename: file.name,
                        content_base64: base64Data,
                        default_profile: agentGlobalProfile ? agentGlobalProfile.value : 'all',
                        default_role_ids: agentGlobalRole ? agentGlobalRole.value : ''
                    })
                });
                const data = await res.json();
                if (data.success && Array.isArray(data.agents)) {
                    const added = addAgentsToOverview(data.agents);
                    logToConsole(`Loaded ${added} agent(s) from ${file.name}.`, 'success');
                } else {
                    logToConsole(`Failed to parse file: ${data.message}`, 'error');
                }
            };
            reader.readAsDataURL(file);
        } catch (err) {
            logToConsole(`Error uploading file: ${err.message}`, 'error');
        }
    }

    if (fileAgentsInput) {
        fileAgentsInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleAgentFile(e.target.files[0]);
                fileAgentsInput.value = '';
            }
        });
    }

    if (excelAgentDropZone) {
        excelAgentDropZone.addEventListener('click', () => {
            if (fileAgentsInput) fileAgentsInput.click();
        });
        excelAgentDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            excelAgentDropZone.classList.add('drag-over');
        });
        excelAgentDropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            excelAgentDropZone.classList.remove('drag-over');
        });
        excelAgentDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            excelAgentDropZone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleAgentFile(e.dataTransfer.files[0]);
            }
        });
    }

    // 4. Batch Actions
    if (agentSelectAll) {
        agentSelectAll.addEventListener('change', () => {
            const checked = agentSelectAll.checked;
            agentOverviewRows.forEach(r => r.selected = checked);
            renderAgentOverview();
        });
    }

    if (btnApplyBatchType && agentBatchType) {
        btnApplyBatchType.addEventListener('click', () => {
            const targetType = agentBatchType.value;
            let count = 0;
            agentOverviewRows.forEach(r => {
                if (r.selected) {
                    r.profile = targetType;
                    count++;
                }
            });
            if (count === 0) {
                logToConsole('Please select one or more agents with the checkboxes first.', 'warn');
                return;
            }
            renderAgentOverview();
            logToConsole(`Updated Account Type to '${targetType}' for ${count} selected agent(s).`, 'info');
        });
    }

    if (btnApplyBatchRole && agentBatchRole) {
        btnApplyBatchRole.addEventListener('click', () => {
            const targetRoleId = agentBatchRole.value;
            if (!targetRoleId) {
                logToConsole('Please select a Role from the dropdown first.', 'warn');
                return;
            }
            const roleObj = (platformMetadata.roles || []).find(r => r.id == targetRoleId);
            const roleName = roleObj ? roleObj.name : targetRoleId;

            let count = 0;
            agentOverviewRows.forEach(r => {
                if (r.selected) {
                    r.role_id = targetRoleId;
                    count++;
                }
            });
            if (count === 0) {
                logToConsole('Please select one or more agents with the checkboxes first.', 'warn');
                return;
            }
            renderAgentOverview();
            logToConsole(`Updated Role to '${roleName}' for ${count} selected agent(s).`, 'info');
        });
    }

    if (btnDeleteSelectedAgents) {
        btnDeleteSelectedAgents.addEventListener('click', () => {
            const initialLen = agentOverviewRows.length;
            agentOverviewRows = agentOverviewRows.filter(r => !r.selected);
            const removed = initialLen - agentOverviewRows.length;
            if (removed === 0) {
                logToConsole('No agents selected to delete.', 'warn');
                return;
            }
            renderAgentOverview();
            logToConsole(`Removed ${removed} selected agent(s) from the list.`, 'system');
        });
    }

    // 5. Render Overview Table
    function renderAgentOverview() {
        if (!agentGridTbody) return;
        agentGridTbody.innerHTML = '';

        const total = agentOverviewRows.length;
        const selected = agentOverviewRows.filter(r => r.selected).length;

        if (agentTotalBadge) agentTotalBadge.textContent = `${total} Agent${total === 1 ? '' : 's'}`;
        if (agentSelectedCount) agentSelectedCount.textContent = selected;
        if (agentSelectAll) {
            agentSelectAll.checked = total > 0 && selected === total;
            agentSelectAll.indeterminate = selected > 0 && selected < total;
        }

        if (btnExecuteCreateAgents) {
            btnExecuteCreateAgents.textContent = `Execute Agent Creation (${total} Agent${total === 1 ? '' : 's'})`;
            btnExecuteCreateAgents.disabled = total === 0;
        }

        if (total === 0) {
            if (agentGridEmptyState) agentGridEmptyState.style.display = 'block';
            return;
        }

        if (agentGridEmptyState) agentGridEmptyState.style.display = 'none';

        const rolesList = platformMetadata.roles || [];

        agentOverviewRows.forEach((row, idx) => {
            const tr = document.createElement('tr');
            if (row.selected) tr.style.background = 'rgba(56, 189, 248, 0.05)';

            // Checkbox
            const tdCheck = document.createElement('td');
            tdCheck.style.textAlign = 'center';
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.checked = !!row.selected;
            chk.style.cursor = 'pointer';
            chk.addEventListener('change', () => {
                row.selected = chk.checked;
                const sel = agentOverviewRows.filter(r => r.selected).length;
                if (agentSelectedCount) agentSelectedCount.textContent = sel;
                if (agentSelectAll) {
                    agentSelectAll.checked = sel === total;
                    agentSelectAll.indeterminate = sel > 0 && sel < total;
                }
                tr.style.background = row.selected ? 'rgba(56, 189, 248, 0.05)' : '';
            });
            tdCheck.appendChild(chk);
            tr.appendChild(tdCheck);

            // Index
            const tdIdx = document.createElement('td');
            tdIdx.style.textAlign = 'center';
            tdIdx.style.color = 'var(--text-secondary)';
            tdIdx.textContent = idx + 1;
            tr.appendChild(tdIdx);

            // Email
            const tdEmail = document.createElement('td');
            tdEmail.style.fontWeight = '500';
            tdEmail.style.color = '#38bdf8';
            tdEmail.style.fontFamily = "'JetBrains Mono', monospace";
            tdEmail.textContent = row.email;
            tr.appendChild(tdEmail);

            // Nick Name (Editable Input)
            const tdNick = document.createElement('td');
            const inputNick = document.createElement('input');
            inputNick.type = 'text';
            inputNick.className = 'form-input';
            inputNick.style.padding = '4px 8px';
            inputNick.style.fontSize = '0.82rem';
            inputNick.style.height = '32px';
            inputNick.placeholder = 'Optional';
            inputNick.value = row.nick_name || '';
            inputNick.addEventListener('input', (e) => {
                row.nick_name = e.target.value.trim();
            });
            tdNick.appendChild(inputNick);
            tr.appendChild(tdNick);

            // Account Type (Dropdown)
            const tdType = document.createElement('td');
            const selectType = document.createElement('select');
            selectType.className = 'form-select';
            selectType.style.padding = '4px 8px';
            selectType.style.fontSize = '0.82rem';
            selectType.innerHTML = `
                <option value="all" ${row.profile === 'all' ? 'selected' : ''}>All Channels / 全渠道 (all)</option>
                <option value="callcenter" ${row.profile === 'callcenter' ? 'selected' : ''}>Call Center / 呼叫中心 (callcenter)</option>
                <option value="im" ${row.profile === 'im' ? 'selected' : ''}>Online IM / 在线客服 (im)</option>
            `;
            selectType.addEventListener('change', (e) => {
                row.profile = e.target.value;
            });
            tdType.appendChild(selectType);
            tr.appendChild(tdType);

            // Role (Dropdown)
            const tdRole = document.createElement('td');
            const selectRole = document.createElement('select');
            selectRole.className = 'form-select';
            selectRole.style.padding = '4px 8px';
            selectRole.style.fontSize = '0.82rem';

            if (rolesList.length === 0) {
                const opt = document.createElement('option');
                opt.value = row.role_id || '';
                opt.textContent = row.role_id ? `Role ID: ${row.role_id}` : 'Default (客服)';
                selectRole.appendChild(opt);
            } else {
                rolesList.forEach(r => {
                    const opt = document.createElement('option');
                    opt.value = r.id;
                    opt.textContent = `${r.name}`;
                    if (row.role_id == r.id) opt.selected = true;
                    selectRole.appendChild(opt);
                });
            }
            selectRole.addEventListener('change', (e) => {
                row.role_id = e.target.value;
            });
            tdRole.appendChild(selectRole);
            tr.appendChild(tdRole);

            // Status Badge
            const tdStatus = document.createElement('td');
            tdStatus.style.textAlign = 'center';
            const badge = document.createElement('span');
            badge.id = `agent-overview-status-${idx}`;
            const st = row.status || 'ready';
            badge.className = `badge-status badge-${st === 'success' ? 'success' : (st === 'failed' ? 'failed' : 'ready')}`;
            badge.textContent = st === 'success' ? '✓ Created' : (st === 'failed' ? '✕ Failed' : 'Ready');
            tdStatus.appendChild(badge);
            tr.appendChild(tdStatus);

            // Action (Delete)
            const tdAction = document.createElement('td');
            tdAction.style.textAlign = 'center';
            const btnDel = document.createElement('button');
            btnDel.type = 'button';
            btnDel.className = 'btn-tool';
            btnDel.textContent = '✕';
            btnDel.style.padding = '2px 6px';
            btnDel.style.color = '#ff5555';
            btnDel.title = 'Remove';
            btnDel.addEventListener('click', () => {
                agentOverviewRows.splice(idx, 1);
                renderAgentOverview();
            });
            tdAction.appendChild(btnDel);
            tr.appendChild(tdAction);

            agentGridTbody.appendChild(tr);
        });
    }

    // 6. Execute Batch Creation
    if (btnExecuteCreateAgents) {
        btnExecuteCreateAgents.addEventListener('click', async () => {
            const authScript = document.getElementById('global-auth-script').value.trim();
            if (!authScript) {
                logToConsole('Error: Please provide your Global Authentication Script first.', 'error');
                return;
            }

            if (agentOverviewRows.length === 0) {
                logToConsole('Error: No agents in the overview list to create.', 'error');
                return;
            }

            const total = agentOverviewRows.length;
            btnExecuteCreateAgents.disabled = true;
            btnExecuteCreateAgents.textContent = `Creating Agents (0/${total})...`;
            logToConsole(`Initiating batch creation of ${total} Agent account(s)...`, 'system');

            // Reset statuses
            agentOverviewRows.forEach((item, i) => {
                item.status = 'ready';
                const badge = document.getElementById(`agent-overview-status-${i}`);
                if (badge) {
                    badge.className = 'badge-status badge-uploading';
                    badge.textContent = 'Pending...';
                }
            });

            const password = agentGlobalPassword ? agentGlobalPassword.value.trim() || 'Pass2026' : 'Pass2026';
            const defaultGroupId = platformMetadata.default_group_id ? [platformMetadata.default_group_id] : [1688021];
            const defaultDeptId = platformMetadata.default_dept_id ? [platformMetadata.default_dept_id] : [1668261];

            const preparedAgents = agentOverviewRows.map(r => ({
                email: r.email,
                nick_name: r.nick_name || '',
                name: r.nick_name || '',
                profile: r.profile || 'all',
                agent_role_ids: r.role_id ? [r.role_id] : (agentGlobalRole && agentGlobalRole.value ? [agentGlobalRole.value] : [1694511]),
                password: password,
                user_group_ids: defaultGroupId,
                department_ids: defaultDeptId
            }));

            try {
                const response = await fetch('/api/create-agents', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        auth_script: authScript,
                        defaults: {
                            password: password,
                            user_group_ids: defaultGroupId,
                            department_ids: defaultDeptId
                        },
                        agents: preparedAgents
                    })
                });

                if (!response.ok) {
                    const text = await response.text();
                    try {
                        const errJson = JSON.parse(text);
                        logToConsole(`Batch creation failed: ${errJson.message}`, 'error');
                    } catch {
                        logToConsole(`Batch creation failed: ${text}`, 'error');
                    }
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.status === 'progress') {
                                const idx = data.index;
                                if (agentOverviewRows[idx]) {
                                    agentOverviewRows[idx].status = data.success ? 'success' : 'failed';
                                }
                                const badge = document.getElementById(`agent-overview-status-${idx}`);
                                if (badge) {
                                    badge.className = `badge-status badge-${data.success ? 'success' : 'failed'}`;
                                    badge.textContent = data.success ? '✓ Created' : '✕ Failed';
                                }
                                btnExecuteCreateAgents.textContent = `Creating Agents (${idx + 1}/${total})...`;
                                logToConsole(data.message, data.success ? 'success' : 'error');
                            } else if (data.status === 'done') {
                                logToConsole(data.message, 'success');
                            } else if (data.status === 'error') {
                                if (data.index != null) {
                                    const idx = data.index;
                                    if (agentOverviewRows[idx]) agentOverviewRows[idx].status = 'failed';
                                    const badge = document.getElementById(`agent-overview-status-${idx}`);
                                    if (badge) {
                                        badge.className = 'badge-status badge-failed';
                                        badge.textContent = '✕ Failed';
                                    }
                                }
                                logToConsole(`Error: ${data.message}`, 'error');
                            } else {
                                logToConsole(data.message, 'system');
                            }
                        } catch (e) {
                            logToConsole(line, 'system');
                        }
                    }
                }
            } catch (err) {
                logToConsole(`Agent creation failed: ${err.message}`, 'error');
            } finally {
                btnExecuteCreateAgents.disabled = false;
                btnExecuteCreateAgents.textContent = `Execute Agent Creation (${total} Agents)`;
            }
        });
    }

    renderAgentOverview();

    // API calls
    const btnMigrateFields = document.getElementById('btn-migrate-fields');
    const btnMigrateTemplate = document.getElementById('btn-migrate-template');
    const btnCreateGroups = document.getElementById('btn-create-groups');
    const btnAssignAgents = document.getElementById('btn-assign-agents');

    btnMigrateFields.addEventListener('click', async () => {
        const authScript = document.getElementById('global-auth-script').value.trim();
        const rawData = document.getElementById('f-raw').value.trim();

        if (!authScript || !rawData) {
            logToConsole('Error: Please provide both the Auth Script and Raw JSON Data.', 'error');
            return;
        }

        btnMigrateFields.disabled = true;
        btnMigrateFields.textContent = 'Processing...';
        logToConsole('Initiating field migration...', 'system');

        try {
            const response = await fetch('/api/migrate-fields', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    auth_script: authScript,
                    raw_data: rawData
                })
            });

            if (!response.ok) {
                const text = await response.text();
                try {
                    const errJson = JSON.parse(text);
                    logToConsole(`Migration failed: ${errJson.message}`, 'error');
                } catch {
                    logToConsole(`Migration failed: ${text}`, 'error');
                }
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.status === 'progress') {
                            btnMigrateFields.textContent = `Processing (${data.index + 1}/${data.total})...`;
                            logToConsole(data.message, 'info');
                        } else if (data.status === 'done') {
                            logToConsole(data.message, 'success');
                        } else if (data.status === 'error') {
                            logToConsole(data.message, 'error');
                        } else if (data.status === 'warn') {
                            logToConsole(data.message, 'warning');
                        } else {
                            logToConsole(data.message || line, data.status || 'system');
                        }
                    } catch (e) {
                        logToConsole(line, 'system');
                    }
                }
            }
        } catch (err) {
            logToConsole(`Request failed: ${err.message}`, 'error');
        } finally {
            btnMigrateFields.disabled = false;
            btnMigrateFields.textContent = 'Execute Field Migration';
        }
    });

    btnMigrateTemplate.addEventListener('click', async () => {
        const tenantAPSScript = document.getElementById('t-auth-a').value.trim();
        const tenantBPSScript = document.getElementById('t-auth-b').value.trim();
        const tenantBFields = document.getElementById('t-fields').value.trim();

        if (!tenantAPSScript || !tenantBPSScript || !tenantBFields) {
            logToConsole('Error: Please provide all three inputs.', 'error');
            return;
        }

        btnMigrateTemplate.disabled = true;
        btnMigrateTemplate.textContent = 'Processing...';
        logToConsole('Initiating template mapping and migration...', 'system');

        try {
            const response = await fetch('/api/migrate-template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tenant_a_ps1: tenantAPSScript,
                    tenant_b_ps1: tenantBPSScript,
                    tenant_b_fields: tenantBFields
                })
            });

            const result = await response.json();

            if (result.success) {
                logToConsole(result.message, 'success');
            } else {
                logToConsole(`Failed: ${result.message}`, 'error');
            }
        } catch (err) {
            logToConsole(`Request failed: ${err.message}`, 'error');
        } finally {
            btnMigrateTemplate.disabled = false;
            btnMigrateTemplate.textContent = 'Execute Template Migration';
        }
    });

    // ==========================================
    // CREATE TICKET TEMPLATES MODULE
    // ==========================================
    function initCreateTicketTemplates() {
        const tplPasteBox = document.getElementById('tpl-paste-box');
        const tplCounterTemplates = document.getElementById('tpl-counter-templates');
        const tplCounterFields = document.getElementById('tpl-counter-fields');
        const tplValidationBadge = document.getElementById('tpl-validation-badge');
        const tplPreviewContainer = document.getElementById('tpl-preview-container');
        const tplPreviewGrid = document.getElementById('tpl-preview-grid');
        const tplStrictGuardAlert = document.getElementById('tpl-strict-guard-alert');
        const tplStrictGuardMsg = document.getElementById('tpl-strict-guard-msg');
        const btnTplRefreshFields = document.getElementById('btn-tpl-refresh-fields');
        const btnTplSampleData = document.getElementById('btn-tpl-sample-data');
        const btnTplClear = document.getElementById('btn-tpl-clear');
        const btnGotoCreateFields = document.getElementById('btn-goto-create-fields');
        const btnExecuteCreateTemplates = document.getElementById('btn-execute-create-templates');

        if (!tplPasteBox || !btnExecuteCreateTemplates) return;

        const escapeHtml = str => String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);

        let localTenantTicketFields = null;
        let parsedTemplatesList = [];
        let parseDebounceTimer = null;
        let isStrictGuardValid = false;

        const sampleTemplateData = `Template: Vehicle Complaint Ticket
VIN (#28101)\ttrue
Car Model (field_28102)\tfalse
Dealer Code*
#28104\toptional
Purchase Date

Template: Periodic Maintenance Ticket
Plate Number\trequired
Current Mileage\toptional
Service Advisor
Maintenance Type*`;

        async function fetchTenantTicketFields(silent = false) {
            const authScript = document.getElementById('global-auth-script')?.value.trim();
            if (!authScript) {
                if (!silent) logToConsole('Please enter Global Authentication Script first to fetch tenant fields.', 'warning');
                updateValidationUI(false, "No Auth Script", {});
                return null;
            }

            if (!silent) logToConsole('Fetching current ticket fields from tenant to validate templates...', 'system');
            if (btnTplRefreshFields) btnTplRefreshFields.disabled = true;

            try {
                const res = await fetch('/api/fetch-custom-fields', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ auth_script: authScript, field_owner: 'Ticket' })
                });
                const data = await res.json();
                if (data.success && data.fields_json) {
                    localTenantTicketFields = data.fields_json;
                    if (!silent) logToConsole(`Successfully fetched ${data.count} ticket fields from tenant.`, 'success');
                    parseAndValidateTemplates();
                    return data.fields_json;
                } else {
                    if (!silent) logToConsole(`Failed to fetch tenant fields: ${data.message}`, 'error');
                }
            } catch (err) {
                if (!silent) logToConsole(`Error connecting to tenant: ${err.message}`, 'error');
            } finally {
                if (btnTplRefreshFields) btnTplRefreshFields.disabled = false;
            }
            return null;
        }

        async function parseAndValidateTemplates() {
            const text = tplPasteBox.value.trim();
            if (!text) {
                parsedTemplatesList = [];
                isStrictGuardValid = false;
                tplCounterTemplates.textContent = 'Templates: 0';
                tplCounterFields.textContent = 'Total Fields: 0';
                tplValidationBadge.innerHTML = '<span class="badge-status badge-neutral">ℹ️ Waiting for input</span>';
                tplPreviewContainer.style.display = 'none';
                tplStrictGuardAlert.style.display = 'none';
                btnExecuteCreateTemplates.textContent = 'Create Ticket Templates (0 Templates)';
                btnExecuteCreateTemplates.disabled = true;
                return;
            }

            const authScript = document.getElementById('global-auth-script')?.value.trim();

            try {
                const res = await fetch('/api/parse-ticket-templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: text,
                        auth_script: authScript,
                        tenant_fields: localTenantTicketFields
                    })
                });

                const data = await res.json();
                if (data.success) {
                    parsedTemplatesList = data.templates || [];
                    const count = data.count || 0;
                    const totalFields = data.total_fields || 0;
                    tplCounterTemplates.textContent = `Templates: ${count}`;
                    tplCounterFields.textContent = `Total Fields: ${totalFields}`;

                    renderPreviewCards(parsedTemplatesList, data.matched_fields || [], data.missing_by_template || {});

                    if (localTenantTicketFields || authScript) {
                        isStrictGuardValid = data.is_valid;
                        updateValidationUI(data.is_valid, data.message, data.missing_by_template || {});
                    } else {
                        isStrictGuardValid = true; // No auth connected yet
                        tplValidationBadge.innerHTML = '<span class="badge-status badge-neutral">ℹ️ Enter Auth to validate fields</span>';
                        tplStrictGuardAlert.style.display = 'none';
                        btnExecuteCreateTemplates.disabled = count === 0;
                        btnExecuteCreateTemplates.textContent = `Create Ticket Templates (${count} Template${count > 1 ? 's' : ''})`;
                    }
                } else {
                    parsedTemplatesList = [];
                    isStrictGuardValid = false;
                    tplValidationBadge.innerHTML = `<span class="badge-status badge-error">❌ Parse error</span>`;
                    btnExecuteCreateTemplates.disabled = true;
                }
            } catch (err) {
                console.error("Error parsing templates:", err);
            }
        }

        function updateValidationUI(isValid, msg, missingByTemplate) {
            const count = parsedTemplatesList.length;
            const missingEntries = Object.entries(missingByTemplate || {});

            if (isValid) {
                tplValidationBadge.innerHTML = '<span class="badge-status badge-ready">✅ All Fields Matched</span>';
                tplStrictGuardAlert.style.display = 'none';
                btnExecuteCreateTemplates.disabled = count === 0;
                btnExecuteCreateTemplates.textContent = `Create Ticket Templates (${count} Template${count > 1 ? 's' : ''})`;
            } else if (missingEntries.length > 0) {
                const totalMissing = missingEntries.reduce((acc, [, list]) => acc + list.length, 0);
                tplValidationBadge.innerHTML = `<span class="badge-status badge-error">🛡️ Missing ${totalMissing} Field(s)</span>`;
                tplStrictGuardAlert.style.display = 'block';

                let detailsHtml = '<ul style="margin: 6px 0 0 16px; padding: 0;">';
                for (const [tplName, missingList] of missingEntries) {
                    detailsHtml += `<li><b>${escapeHtml(tplName)}</b>: Missing <code>${missingList.map(escapeHtml).join('</code>, <code>')}</code></li>`;
                }
                detailsHtml += '</ul>';
                tplStrictGuardMsg.innerHTML = detailsHtml;

                btnExecuteCreateTemplates.disabled = true;
                btnExecuteCreateTemplates.textContent = `Blocked by Strict Guard (Resolve Missing Fields)`;
            } else {
                tplValidationBadge.innerHTML = '<span class="badge-status badge-neutral">ℹ️ Enter Auth to check fields</span>';
                tplStrictGuardAlert.style.display = 'none';
                btnExecuteCreateTemplates.disabled = count === 0;
                btnExecuteCreateTemplates.textContent = `Create Ticket Templates (${count} Template${count > 1 ? 's' : ''})`;
            }
        }

        function renderPreviewCards(templates, matchedFields, missingByTemplate) {
            if (!templates || templates.length === 0) {
                tplPreviewContainer.style.display = 'none';
                tplPreviewGrid.innerHTML = '';
                return;
            }

            tplPreviewContainer.style.display = 'block';
            let html = '';
            for (const tpl of templates) {
                const missingList = (missingByTemplate[tpl.name] || []).map(f => f.toLowerCase());
                const missingSet = new Set(missingList);

                html += `
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 12px 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-weight: 600; color: #fff; font-size: 0.95rem;">📋 ${escapeHtml(tpl.name)}</span>
                            <span style="font-size: 0.75rem; color: var(--accent-blue, #64B5F6); background: rgba(100,181,246,0.1); padding: 2px 8px; border-radius: 12px;">${tpl.fields.length} Fields</span>
                        </div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                `;

                for (const f of tpl.fields) {
                    const isMissing = missingSet.has(f.title.toLowerCase()) || 
                                      (f.target_id && missingSet.has(`#${f.target_id}`)) || 
                                      (f.target_name && missingSet.has(f.target_name.toLowerCase()));
                    const reqBadge = f.required ? ' <span style="color: #ff6b6b; font-weight: bold;">*</span>' : '';
                    let pillStyle = "background: rgba(255,255,255,0.06); color: #cbd5e0; border: 1px solid rgba(255,255,255,0.1);";
                    if (isMissing) {
                        pillStyle = "background: rgba(245, 101, 101, 0.2); color: #feb2b2; border: 1px solid rgba(245, 101, 101, 0.4);";
                    } else if (f.has_duplicates) {
                        pillStyle = "background: rgba(236, 201, 75, 0.15); color: #fbd38d; border: 1px solid rgba(236, 201, 75, 0.4);";
                    }

                    let label = f.display_title || f.title;
                    if (f.resolved_id) {
                        label += ` (#${f.resolved_id})`;
                    } else if (f.target_id && !label.includes(f.target_id)) {
                        label += ` (#${f.target_id})`;
                    }

                    let hoverTitle = 'Matched';
                    if (isMissing) {
                        hoverTitle = 'Missing from tenant!';
                    } else if (f.has_duplicates) {
                        hoverTitle = `Duplicate title in tenant! Matched ID #${f.resolved_id}. Candidate IDs: ${(f.duplicate_ids || []).join(', ')}`;
                    }

                    html += `<span style="font-size: 0.78rem; padding: 2px 8px; border-radius: 4px; ${pillStyle}" title="${escapeHtml(hoverTitle)}">${escapeHtml(label)}${reqBadge}</span>`;
                }

                html += `
                        </div>
                    </div>
                `;
            }
            tplPreviewGrid.innerHTML = html;
        }

        tplPasteBox.addEventListener('input', () => {
            clearTimeout(parseDebounceTimer);
            parseDebounceTimer = setTimeout(() => {
                parseAndValidateTemplates();
            }, 300);
        });

        btnTplSampleData?.addEventListener('click', () => {
            tplPasteBox.value = sampleTemplateData;
            parseAndValidateTemplates();
        });

        btnTplClear?.addEventListener('click', () => {
            tplPasteBox.value = '';
            parseAndValidateTemplates();
        });

        btnTplRefreshFields?.addEventListener('click', () => {
            fetchTenantTicketFields(false);
        });

        btnGotoCreateFields?.addEventListener('click', () => {
            const subTabBtn = document.querySelector('.sub-tab-btn[data-target="tab-create-fields"]');
            if (subTabBtn) subTabBtn.click();
        });

        btnExecuteCreateTemplates.addEventListener('click', async () => {
            const authScript = document.getElementById('global-auth-script')?.value.trim();
            if (!authScript) {
                logToConsole('Error: Please enter the Global Authentication Script first.', 'error');
                return;
            }

            if (parsedTemplatesList.length === 0) {
                logToConsole('Error: No template definitions to create.', 'error');
                return;
            }

            if (!isStrictGuardValid && localTenantTicketFields) {
                logToConsole('Blocked by Strict Guard: Cannot create templates while referenced fields are missing in tenant.', 'error');
                return;
            }

            btnExecuteCreateTemplates.disabled = true;
            btnExecuteCreateTemplates.textContent = 'Creating Templates...';
            logToConsole(`Initiating batch creation for ${parsedTemplatesList.length} template(s)...`, 'system');

            try {
                const response = await fetch('/api/batch-create-ticket-templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        auth_script: authScript,
                        templates: parsedTemplatesList,
                        tenant_fields: localTenantTicketFields
                    })
                });

                if (!response.ok) {
                    const text = await response.text();
                    try {
                        const errJson = JSON.parse(text);
                        logToConsole(`Creation failed: ${errJson.message}`, 'error');
                    } catch {
                        logToConsole(`Creation failed: ${text}`, 'error');
                    }
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.status === 'progress') {
                                btnExecuteCreateTemplates.textContent = `Creating (${data.data?.index || 1}/${parsedTemplatesList.length})...`;
                                logToConsole(data.message, 'info');
                            } else if (data.status === 'done') {
                                logToConsole(data.message, 'success');
                            } else if (data.status === 'error') {
                                logToConsole(data.message, 'error');
                            } else if (data.status === 'warn') {
                                logToConsole(data.message, 'warning');
                            } else {
                                logToConsole(data.message || line, data.status || 'system');
                            }
                        } catch (e) {
                            logToConsole(line, 'system');
                        }
                    }
                }
            } catch (err) {
                logToConsole(`Request failed: ${err.message}`, 'error');
            } finally {
                btnExecuteCreateTemplates.disabled = false;
                btnExecuteCreateTemplates.textContent = `Create Ticket Templates (${parsedTemplatesList.length} Templates)`;
            }
        });

        // Pre-fetch fields silently if Global Auth script is already populated
        const globalAuthScript = document.getElementById('global-auth-script');
        if (globalAuthScript && globalAuthScript.value.trim()) {
            fetchTenantTicketFields(true);
        }
    }

    initCreateTicketTemplates();

    btnCreateGroups.addEventListener('click', async () => {
        const authScript = document.getElementById('global-auth-script').value.trim();
        const namesList = document.getElementById('g-names').value.trim();

        if (!authScript || !namesList) {
            logToConsole('Error: Please provide both the Auth Script and the List of Names.', 'error');
            return;
        }

        btnCreateGroups.disabled = true;
        btnCreateGroups.textContent = 'Processing...';
        logToConsole('Initiating agent groups creation...', 'system');

        try {
            const response = await fetch('/api/create-agent-groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    auth_script: authScript,
                    names_list: namesList
                })
            });

            if (!response.ok) {
                // Try to read error message if it's a 400/500
                const text = await response.text();
                try {
                    const data = JSON.parse(text);
                    logToConsole(`Failed: ${data.message}`, 'error');
                } catch {
                    logToConsole(`Failed: ${text}`, 'error');
                }
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.status === 'error') {
                            logToConsole(`Error: ${data.message}`, 'error');
                        } else if (data.status === 'done') {
                            logToConsole(data.message, 'success');
                        } else {
                            logToConsole(data.message, 'system');
                        }
                    } catch (e) {
                        logToConsole(line, 'system');
                    }
                }
            }
        } catch (err) {
            logToConsole(`Request failed: ${err.message}`, 'error');
        } finally {
            btnCreateGroups.disabled = false;
            btnCreateGroups.textContent = 'Execute Group Creation';
        }
    });

    // Fetch Groups & Agents from Tenant
    const btnFetchBoth = document.getElementById('btn-fetch-both');
    btnFetchBoth.addEventListener('click', async () => {
        const authScript = document.getElementById('global-auth-script').value.trim();

        if (!authScript) {
            logToConsole('Error: Please paste your Global Authentication Script first.', 'error');
            return;
        }

        btnFetchBoth.disabled = true;
        btnFetchBoth.textContent = 'Fetching from Tenant...';
        logToConsole('Fetching Groups & Agents from API...', 'system');

        try {
            const response = await fetch('/api/fetch-tenant-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ auth_script: authScript })
            });

            const result = await response.json();

            if (result.success) {
                const groupsTextarea = document.getElementById('a-groups-json');
                const agentsTextarea = document.getElementById('a-agents-json');

                groupsTextarea.value = JSON.stringify(result.groups_json, null, 2);
                agentsTextarea.value = JSON.stringify(result.agents_json, null, 2);

                // Trigger localStorage save
                groupsTextarea.dispatchEvent(new Event('input'));
                agentsTextarea.dispatchEvent(new Event('input'));

                logToConsole(result.message, 'success');
            } else {
                logToConsole(`Error: ${result.message}`, 'error');
            }
        } catch (err) {
            logToConsole(`Request failed: ${err.message}`, 'error');
        } finally {
            btnFetchBoth.disabled = false;
            btnFetchBoth.textContent = 'Fetch Groups & Agents from Tenant';
        }
    });

    btnAssignAgents.addEventListener('click', async () => {
        const authScript = document.getElementById('global-auth-script').value.trim();
        const groupsJson = document.getElementById('a-groups-json').value.trim();
        const agentsJson = document.getElementById('a-agents-json').value.trim();
        const mappingCsv = document.getElementById('a-mapping').value.trim();

        if (!authScript || !groupsJson || !agentsJson || !mappingCsv) {
            logToConsole('Error: Please provide all inputs for Assign Agents.', 'error');
            return;
        }

        btnAssignAgents.disabled = true;
        btnAssignAgents.textContent = 'Processing...';
        logToConsole('Initiating agent assignments...', 'system');

        try {
            const response = await fetch('/api/assign-agents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    auth_script: authScript,
                    groups_json: groupsJson,
                    agents_json: agentsJson,
                    mapping_csv: mappingCsv
                })
            });

            if (!response.ok) {
                const text = await response.text();
                try {
                    const data = JSON.parse(text);
                    logToConsole(`Failed: ${data.message}`, 'error');
                } catch {
                    logToConsole(`Failed: ${text}`, 'error');
                }
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.status === 'error') {
                            logToConsole(`Error: ${data.message}`, 'error');
                        } else if (data.status === 'done') {
                            logToConsole(data.message, 'success');
                        } else {
                            logToConsole(data.message, 'system');
                        }
                    } catch (e) {
                        logToConsole(line, 'system');
                    }
                }
            }
        } catch (err) {
            logToConsole(`Request failed: ${err.message}`, 'error');
        } finally {
            btnAssignAgents.disabled = false;
            btnAssignAgents.textContent = 'Execute Agent Assignment';
        }
    });

    // ==========================================
    // Voice Library Management
    // ==========================================
    let scannedVoiceFiles = [];

    const vDirInput = document.getElementById('v-dir');
    const vNamingMode = document.getElementById('v-naming-mode');
    const vPrefix = document.getElementById('v-prefix');
    const vSuffix = document.getElementById('v-suffix');
    const vPattern = document.getElementById('v-pattern');
    const vPatternGroup = document.getElementById('v-pattern-group');
    const vTargetUrl = document.getElementById('v-target-url');
    const vCdpPort = document.getElementById('v-cdp-port');
    const vUsername = document.getElementById('v-username');
    const vPassword = document.getElementById('v-password');
    const btnScanVoice = document.getElementById('btn-scan-voice');
    const btnUploadVoice = document.getElementById('btn-upload-voice');
    const btnRetryFailed = document.getElementById('btn-retry-failed');
    const btnRecalculate = document.getElementById('btn-recalculate-names');
    const btnSelectAll = document.getElementById('btn-select-all');
    const btnDeselectAll = document.getElementById('btn-deselect-all');
    const thCheckAll = document.getElementById('th-check-all');
    const voiceTableBody = document.getElementById('voice-table-body');
    const vSelectionCount = document.getElementById('v-selection-count');

    // Naming mode UI adjustment
    function updateNamingModeUI() {
        const mode = vNamingMode.value;
        if (mode === 'custom') {
            vPatternGroup.style.display = 'flex';
        } else {
            vPatternGroup.style.display = 'none';
        }
    }
    vNamingMode.addEventListener('change', () => {
        updateNamingModeUI();
        recalculateNamesInPlace();
    });
    updateNamingModeUI();

    [vPrefix, vSuffix, vPattern].forEach(input => {
        if (input) {
            input.addEventListener('input', () => {
                recalculateNamesInPlace();
            });
        }
    });

    // Auto-derive target Voice URL if empty when global auth script updates
    function updateVoiceTargetUrlDefault() {
        const script = globalAuthScriptInput ? (globalAuthScriptInput.value || '') : '';
        if (!script) return;
        const match = script.match(/-Uri\s+["'](https?:\/\/[^/]+)/i);
        if (match && match[1] && vTargetUrl && !vTargetUrl.value) {
            vTargetUrl.placeholder = `${match[1]}/entry/manage/callcenter/voice-list`;
        }
    }
    if (globalAuthScriptInput) {
        globalAuthScriptInput.addEventListener('input', updateVoiceTargetUrlDefault);
        updateVoiceTargetUrlDefault();
    }

    // Recalculate voice names for currently scanned files
    function recalculateNamesInPlace() {
        if (!scannedVoiceFiles.length) return;
        const mode = vNamingMode.value;
        const prefix = vPrefix.value || '';
        const suffix = vSuffix.value || '';
        const pattern = vPattern.value || '';

        scannedVoiceFiles.forEach((file, idx) => {
            const nameWithoutExt = file.filename.substring(0, file.filename.lastIndexOf('.')) || file.filename;
            let newName = nameWithoutExt;

            if (mode === 'exact') {
                newName = nameWithoutExt;
            } else if (mode === 'folder_suffix') {
                newName = file.parent_dir ? `${nameWithoutExt}_${file.parent_dir}` : nameWithoutExt;
            } else if (mode === 'prefix') {
                newName = `${prefix}${nameWithoutExt}`;
            } else if (mode === 'suffix') {
                newName = `${nameWithoutExt}${suffix}`;
            } else if (mode === 'custom' && pattern) {
                newName = pattern.replace('{file}', nameWithoutExt)
                    .replace('{folder}', file.parent_dir || '')
                    .replace('{prefix}', prefix)
                    .replace('{suffix}', suffix);
            }
            file.voice_name = newName;

            const inputElem = document.getElementById(`v-name-input-${idx}`);
            if (inputElem) {
                inputElem.value = newName;
            }
        });
    }

    if (btnRecalculate) {
        btnRecalculate.addEventListener('click', () => {
            recalculateNamesInPlace();
            logToConsole('Recalculated voice names based on current rules.', 'system');
        });
    }

    // Render Preview Table
    function renderVoiceTable() {
        if (!scannedVoiceFiles.length) {
            voiceTableBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 24px;">
                        No audio files found in specified directory.
                    </td>
                </tr>`;
            updateSelectionBadge();
            return;
        }

        voiceTableBody.innerHTML = '';
        scannedVoiceFiles.forEach((file, idx) => {
            const tr = document.createElement('tr');
            tr.id = `v-row-${idx}`;
            tr.innerHTML = `
                <td style="text-align: center;">
                    <input type="checkbox" class="row-checkbox" data-index="${idx}" ${file.selected ? 'checked' : ''}>
                </td>
                <td style="font-weight: 500;">
                    ${escapeHtml(file.filename)}
                </td>
                <td style="color: var(--text-secondary); font-size: 0.8rem;">
                    ${escapeHtml(file.parent_dir || '-')}
                </td>
                <td style="color: var(--text-secondary); font-size: 0.8rem;">
                    ${file.size_mb} MB
                </td>
                <td>
                    <input type="text" id="v-name-input-${idx}" class="table-input" value="${escapeHtml(file.voice_name)}">
                </td>
                <td style="text-align: center;" id="v-status-${idx}">
                    <span class="badge-status ${getStatusBadgeClass(file.status || 'pending')}">${getStatusLabel(file.status || 'pending')}</span>
                </td>
            `;

            // Checkbox event
            const chk = tr.querySelector('.row-checkbox');
            chk.addEventListener('change', (e) => {
                file.selected = e.target.checked;
                updateSelectionBadge();
            });

            // Input edit event
            const inputElem = tr.querySelector('.table-input');
            inputElem.addEventListener('input', (e) => {
                file.voice_name = e.target.value;
            });

            voiceTableBody.appendChild(tr);
        });

        updateSelectionBadge();
    }

    function getStatusBadgeClass(status) {
        if (status === 'uploading') return 'badge-uploading';
        if (status === 'success') return 'badge-success';
        if (status === 'failed') return 'badge-failed';
        return 'badge-pending';
    }

    function getStatusLabel(status) {
        if (status === 'uploading') return 'Uploading...';
        if (status === 'success') return 'Success';
        if (status === 'failed') return 'Failed';
        return 'Pending';
    }

    function updateSelectionBadge() {
        const total = scannedVoiceFiles.length;
        const selected = scannedVoiceFiles.filter(f => f.selected).length;
        vSelectionCount.textContent = `${selected}/${total} selected`;
    }

    function escapeHtml(text) {
        if (!text) return '';
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // Select/Deselect All buttons
    if (btnSelectAll) {
        btnSelectAll.addEventListener('click', () => {
            scannedVoiceFiles.forEach(f => f.selected = true);
            document.querySelectorAll('.row-checkbox').forEach(c => c.checked = true);
            thCheckAll.checked = true;
            updateSelectionBadge();
        });
    }

    if (btnDeselectAll) {
        btnDeselectAll.addEventListener('click', () => {
            scannedVoiceFiles.forEach(f => f.selected = false);
            document.querySelectorAll('.row-checkbox').forEach(c => c.checked = false);
            thCheckAll.checked = false;
            updateSelectionBadge();
        });
    }

    if (thCheckAll) {
        thCheckAll.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            scannedVoiceFiles.forEach(f => f.selected = isChecked);
            document.querySelectorAll('.row-checkbox').forEach(c => c.checked = isChecked);
            updateSelectionBadge();
        });
    }

    // Scan Audio Files Action
    btnScanVoice.addEventListener('click', async () => {
        const dirPath = vDirInput.value.trim();
        if (!dirPath) {
            logToConsole('Error: Please enter an audio directory path to scan.', 'error');
            return;
        }

        btnScanVoice.disabled = true;
        btnScanVoice.textContent = 'Scanning...';
        logToConsole(`Scanning directory: ${dirPath}...`, 'system');

        try {
            const response = await fetch('/api/scan-voice-files', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    dir_path: dirPath,
                    naming_mode: vNamingMode.value,
                    prefix: vPrefix.value,
                    suffix: vSuffix.value,
                    pattern: vPattern.value
                })
            });

            const result = await response.json();
            if (result.success) {
                scannedVoiceFiles = result.files.map(f => ({ ...f, status: 'pending' }));
                renderVoiceTable();
                btnRetryFailed.style.display = 'none';
                logToConsole(`Found ${scannedVoiceFiles.length} audio file(s) ready for preview.`, 'success');
            } else {
                logToConsole(`Scan failed: ${result.message}`, 'error');
            }
        } catch (err) {
            logToConsole(`Scan request error: ${err.message}`, 'error');
        } finally {
            btnScanVoice.disabled = false;
            btnScanVoice.textContent = 'Scan Audio Files';
        }
    });

    // Upload Execution Function
    async function executeVoiceUpload(filesToUpload) {
        if (!filesToUpload.length) {
            logToConsole('Error: No files selected for upload.', 'error');
            return;
        }

        const authScript = globalAuthScriptInput.value.trim();
        const targetUrl = vTargetUrl.value.trim();
        const cdpPort = parseInt(vCdpPort.value) || 9225;
        const username = vUsername.value.trim();
        const password = vPassword.value.trim();

        let customCreds = null;
        if (username && password) {
            customCreds = { username, password };
        }

        btnUploadVoice.disabled = true;
        btnUploadVoice.textContent = 'Uploading...';
        btnRetryFailed.disabled = true;
        logToConsole(`Starting voice upload for ${filesToUpload.length} file(s)...`, 'system');

        try {
            const response = await fetch('/api/upload-voice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    auth_script: authScript,
                    files: filesToUpload,
                    target_url: targetUrl,
                    cdp_port: cdpPort,
                    credentials: customCreds
                })
            });

            if (!response.ok) {
                const text = await response.text();
                logToConsole(`Failed: ${text}`, 'error');
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let failedItemsExist = false;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        const msgType = data.status === 'error' ? 'error' : (data.status === 'done' ? 'success' : 'system');
                        logToConsole(data.message, msgType);

                        // If chunk has item-specific status data
                        if (data.data && data.data.filename) {
                            const filename = data.data.filename;
                            const status = data.data.status;

                            // Find corresponding item in scannedVoiceFiles
                            const fileItem = scannedVoiceFiles.find(f => f.filename === filename);
                            if (fileItem) {
                                fileItem.status = status;
                                const idx = scannedVoiceFiles.indexOf(fileItem);
                                const statusElem = document.getElementById(`v-status-${idx}`);
                                if (statusElem) {
                                    statusElem.innerHTML = `<span class="badge-status ${getStatusBadgeClass(status)}">${getStatusLabel(status)}</span>`;
                                }
                            }

                            if (status === 'failed') {
                                failedItemsExist = true;
                            }
                        }

                        if (data.status === 'done' && data.data && data.data.failed > 0) {
                            failedItemsExist = true;
                        }
                    } catch (e) {
                        logToConsole(line, 'system');
                    }
                }
            }

            if (failedItemsExist) {
                btnRetryFailed.style.display = 'block';
            } else {
                btnRetryFailed.style.display = 'none';
            }

        } catch (err) {
            logToConsole(`Upload request failed: ${err.message}`, 'error');
        } finally {
            btnUploadVoice.disabled = false;
            btnUploadVoice.textContent = 'Execute Voice Upload';
            btnRetryFailed.disabled = false;
        }
    }

    btnUploadVoice.addEventListener('click', () => {
        const selectedFiles = scannedVoiceFiles.filter(f => f.selected);
        executeVoiceUpload(selectedFiles);
    });

    btnRetryFailed.addEventListener('click', () => {
        const failedFiles = scannedVoiceFiles.filter(f => f.status === 'failed');
        if (!failedFiles.length) {
            logToConsole('No failed items found to retry.', 'system');
            return;
        }
        logToConsole(`Retrying ${failedFiles.length} failed file(s)...`, 'system');
        executeVoiceUpload(failedFiles);
    });

    // ==========================================
    // Voice Mode Switcher & Batch TTS Logic
    // ==========================================
    const btnVoiceModeUpload = document.getElementById('btn-voice-mode-upload');
    const btnVoiceModeTts = document.getElementById('btn-voice-mode-tts');
    const panelVoiceModeUpload = document.getElementById('panel-voice-mode-upload');
    const panelVoiceModeTts = document.getElementById('panel-voice-mode-tts');

    const vTtsTimbre = document.getElementById('v-tts-timbre');
    const vTtsCountBadge = document.getElementById('v-tts-count-badge');
    const btnPasteTtsSample = document.getElementById('btn-paste-tts-sample');
    const btnClearTts = document.getElementById('btn-clear-tts');
    const vTtsText = document.getElementById('v-tts-text');
    const vTtsCdpPort = document.getElementById('v-tts-cdp-port');
    const vTtsCdpUrl = document.getElementById('v-tts-cdp-url');
    const btnExecuteTts = document.getElementById('btn-execute-tts');
    const btnStopTts = document.getElementById('btn-stop-tts');

    if (btnVoiceModeUpload && btnVoiceModeTts) {
        btnVoiceModeUpload.addEventListener('click', () => {
            btnVoiceModeUpload.classList.add('active');
            btnVoiceModeTts.classList.remove('active');
            if (panelVoiceModeUpload) panelVoiceModeUpload.style.display = 'block';
            if (panelVoiceModeTts) panelVoiceModeTts.style.display = 'none';
        });

        btnVoiceModeTts.addEventListener('click', () => {
            btnVoiceModeTts.classList.add('active');
            btnVoiceModeUpload.classList.remove('active');
            if (panelVoiceModeUpload) panelVoiceModeUpload.style.display = 'none';
            if (panelVoiceModeTts) {
                panelVoiceModeTts.style.display = 'block';
                if (vTtsText) vTtsText.focus();
            }
        });
    }

    function parseClientTtsText(rawText, defaultTimbre = '小夏') {
        if (!rawText || !rawText.trim()) return [];
        const lines = rawText.split(/\r?\n/);
        const delimiter = rawText.includes('\t') ? '\t' : ',';
        const items = [];
        const headerKeywords = ['语音', '名称', 'name', 'title', 'prompt', 'voice', 'filename'];

        lines.forEach((line) => {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('//')) return;
            const parts = line.split(delimiter).map(p => p.trim().replace(/^["']|["']$/g, ''));
            if (!parts || parts.length === 0) return;

            // Check header on first non-empty line
            if (items.length === 0 && headerKeywords.some(hk => parts[0].toLowerCase().includes(hk))) {
                return;
            }

            const name = parts[0] || `Voice_${items.length + 1}`;
            const content = parts[1] || '';
            const timbre = parts[2] || defaultTimbre || '小夏';

            if (name || content) {
                items.push({ name, content, timbre });
            }
        });

        return items;
    }

    function updateTtsCount() {
        if (!vTtsCountBadge || !vTtsText) return;
        const text = vTtsText.value.trim();
        const timbre = (vTtsTimbre ? vTtsTimbre.value.trim() : '') || '小夏';
        const items = parseClientTtsText(text, timbre);
        const count = items.length;
        vTtsCountBadge.textContent = `${count} Prompt${count === 1 ? '' : 's'} Detected`;
        if (count > 0) {
            vTtsCountBadge.style.color = '#00ffaa';
            vTtsCountBadge.style.borderColor = 'rgba(0, 255, 170, 0.4)';
            vTtsCountBadge.style.background = 'rgba(0, 255, 170, 0.12)';
        } else {
            vTtsCountBadge.style.color = '#00d4ff';
            vTtsCountBadge.style.borderColor = 'rgba(0, 212, 255, 0.3)';
            vTtsCountBadge.style.background = 'rgba(0, 212, 255, 0.15)';
        }
    }

    if (vTtsText) {
        vTtsText.addEventListener('input', updateTtsCount);
    }
    if (vTtsTimbre) {
        vTtsTimbre.addEventListener('input', updateTtsCount);
    }

    if (btnPasteTtsSample && vTtsText) {
        btnPasteTtsSample.addEventListener('click', () => {
            const sample = [
                'welcome_prompt\tWelcome to customer care. How may I assist you today?\t小夏',
                'queue_wait\tAll representatives are currently assisting other callers. Please hold the line.\t小夏',
                'transfer_agent\tTransferring your call to our service specialist. Please wait.\t小夏',
                'afterhours_notice\tOur customer service center is currently closed. Please call back tomorrow.\t小夏'
            ].join('\n');
            vTtsText.value = sample;
            updateTtsCount();
            vTtsText.focus();
            logToConsole('Inserted sample voice prompt definitions into TTS paste area.', 'system');
        });
    }

    if (btnClearTts && vTtsText) {
        btnClearTts.addEventListener('click', () => {
            vTtsText.value = '';
            updateTtsCount();
            vTtsText.focus();
        });
    }

    if (btnExecuteTts) {
        btnExecuteTts.addEventListener('click', async () => {
            const rawText = vTtsText ? vTtsText.value.trim() : '';
            if (!rawText) {
                logToConsole('Error: Please paste or enter voice prompts before executing.', 'warn');
                return;
            }

            const defaultTimbre = (vTtsTimbre ? vTtsTimbre.value.trim() : '') || '小夏';
            const items = parseClientTtsText(rawText, defaultTimbre);
            if (items.length === 0) {
                logToConsole('Error: No valid voice prompt rows could be extracted.', 'error');
                return;
            }

            const cdpPort = vTtsCdpPort && vTtsCdpPort.value ? parseInt(vTtsCdpPort.value, 10) : 9225;
            const cdpUrl = vTtsCdpUrl ? vTtsCdpUrl.value.trim() : '';

            btnExecuteTts.disabled = true;
            btnExecuteTts.textContent = `Creating ${items.length} Voice Prompts...`;
            if (btnStopTts) btnStopTts.style.display = 'inline-block';

            logToConsole(`Connecting to Chrome on port ${cdpPort} to batch create ${items.length} TTS voice files...`, 'system');

            try {
                const resp = await fetch('/api/batch-create-voice-tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        items: items,
                        cdp_port: cdpPort,
                        cdp_url: cdpUrl || null,
                        default_timbre: defaultTimbre
                    })
                });

                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({ message: 'Server returned error ' + resp.status }));
                    logToConsole(`Batch TTS creation failed: ${err.message}`, 'error');
                    return;
                }

                const reader = resp.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            const msgType = data.status === 'error' ? 'error' : (data.status === 'done' ? 'success' : (data.status === 'warn' ? 'warn' : 'system'));
                            logToConsole(data.message, msgType);
                        } catch (_) {
                            logToConsole(line, 'system');
                        }
                    }
                }

            } catch (err) {
                logToConsole(`Batch TTS network error: ${err.message}`, 'error');
            } finally {
                btnExecuteTts.disabled = false;
                btnExecuteTts.textContent = 'Execute Batch TTS Creation';
                if (btnStopTts) btnStopTts.style.display = 'none';
            }
        });
    }

    if (btnStopTts) {
        btnStopTts.addEventListener('click', async () => {
            btnStopTts.disabled = true;
            logToConsole('Sending stop request to Batch TTS creation process...', 'warn');
            try {
                const resp = await fetch('/api/stop-voice-tts', { method: 'POST' });
                const res = await resp.json();
                if (res.stopped) {
                    logToConsole('Stop signal acknowledged by worker.', 'system');
                } else {
                    logToConsole(res.message || 'No active TTS build running.', 'system');
                }
            } catch (err) {
                logToConsole(`Failed to send stop signal: ${err.message}`, 'error');
            } finally {
                btnStopTts.disabled = false;
            }
        });
    }

    // ==========================================
    // IVR Flow Builder Logic
    // ==========================================
    const ivrTemplateSelect = document.getElementById('ivr-template-select');
    const btnLoadIvrTemplate = document.getElementById('btn-load-ivr-template');
    const ivrYamlInput = document.getElementById('ivr-yaml-input');
    const ivrCanvasCount = document.getElementById('ivr-canvas-count');
    const ivrValidBadge = document.getElementById('ivr-valid-badge');
    const ivrNodeCount = document.getElementById('ivr-node-count');
    const ivrRouteCount = document.getElementById('ivr-route-count');
    const btnValidateIvr = document.getElementById('btn-validate-ivr');
    const btnBuildIvr = document.getElementById('btn-build-ivr');
    const ivrCdpPort = document.getElementById('ivr-cdp-port');
    const ivrCdpUrl = document.getElementById('ivr-cdp-url');

    const modalPairIvrTabs = document.getElementById('modal-pair-ivr-tabs');
    const ivrTabPairingList = document.getElementById('ivr-tab-pairing-list');
    const ivrPairTabsWarning = document.getElementById('ivr-pair-tabs-warning');
    const ivrPairDuplicateWarning = document.getElementById('ivr-pair-duplicate-warning');
    const btnRefreshPairTabs = document.getElementById('btn-refresh-pair-tabs');
    const btnClosePairModal = document.getElementById('btn-close-pair-modal');
    const btnCancelPairModal = document.getElementById('btn-cancel-pair-modal');
    const btnConfirmPairBuild = document.getElementById('btn-confirm-pair-build');

    let lastValidatedIvrData = null;

    const IVR_TEMPLATES = {
        multilang_multicanvas: `ivr_name: "Multi-Language Modular IVR (3 Canvases)"
canvases:
  - canvas_name: "Root - Greeting & Language Selection"
    nodes:
      - id: root_start
        type: start
        title: "Start"
        routes:
          default: root_greeting

      - id: root_greeting
        type: voice_playback
        title: "Welcome Greeting"
        audio: "Welcome_MSG_Root"
        routes:
          default: lang_selection

      - id: lang_selection
        type: collect_input
        title: "Select Language"
        audio: "Select_Language_MSG"
        config:
          timeout_seconds: 5
          max_digits: 1
        routes:
          keys:
            "1": lang_judgment
            "2": lang_judgment
          default: lang_judgment
          timeout: root_no_input
          invalid: root_invalid

      - id: lang_judgment
        type: info_judgment
        title: "Language Branch"
        rules:
          - name: "Arabic Track"
            variable: "User Input"
            operator: "Equal"
            value: "1"
            target: transfer_to_ar
          - name: "English Track"
            variable: "User Input"
            operator: "Equal"
            value: "2"
            target: transfer_to_en
        routes:
          default: root_invalid

      - id: transfer_to_ar
        type: voice_playback
        title: "Go to Arabic Flow"
        audio: "Transfer_Arabic_Prompt"
        routes:
          default: root_hangup

      - id: transfer_to_en
        type: voice_playback
        title: "Go to English Flow"
        audio: "Transfer_English_Prompt"
        routes:
          default: root_hangup

      - id: root_no_input
        type: voice_playback
        title: "Root No Input"
        audio: "No_Input_Prompt"
        routes:
          default: lang_selection

      - id: root_invalid
        type: voice_playback
        title: "Root Invalid Input"
        audio: "Invalid_Prompt"
        routes:
          default: lang_selection

      - id: root_hangup
        type: hang_up
        title: "End Call"

  - canvas_name: "Arabic Sub-Flow (Menu & Queues)"
    nodes:
      - id: ar_start
        type: start
        title: "Start"
        routes:
          default: ar_menu

      - id: ar_menu
        type: collect_input
        title: "Arabic Main Menu"
        audio: "AR_MainMenu_MSG"
        config:
          timeout_seconds: 5
          max_digits: 1
        routes:
          keys:
            "1": ar_judgment
            "2": ar_judgment
          default: ar_judgment
          timeout: ar_no_input
          invalid: ar_invalid

      - id: ar_judgment
        type: info_judgment
        title: "Arabic Menu Branch"
        rules:
          - name: "Arabic Sales"
            variable: "User Input"
            operator: "Equal"
            value: "1"
            target: ar_sales_queue
          - name: "Arabic Service"
            variable: "User Input"
            operator: "Equal"
            value: "2"
            target: ar_service_queue
        routes:
          default: ar_invalid

      - id: ar_sales_queue
        type: enter_queue
        title: "Arabic Sales"
        config:
          group_name: "Arabic Sales Team"
        routes:
          default: ar_hangup

      - id: ar_service_queue
        type: enter_queue
        title: "Arabic Service"
        config:
          group_name: "Arabic Service Team"
        routes:
          default: ar_hangup

      - id: ar_no_input
        type: voice_playback
        title: "AR No Input"
        audio: "AR_NoInput_MSG"
        routes:
          default: ar_menu

      - id: ar_invalid
        type: voice_playback
        title: "AR Invalid Option"
        audio: "AR_InvalidOption_MSG"
        routes:
          default: ar_menu

      - id: ar_hangup
        type: hang_up
        title: "End Call"

  - canvas_name: "English Sub-Flow (Menu & Queues)"
    nodes:
      - id: en_start
        type: start
        title: "Start"
        routes:
          default: en_menu

      - id: en_menu
        type: collect_input
        title: "English Main Menu"
        audio: "EN_MainMenu_MSG"
        config:
          timeout_seconds: 5
          max_digits: 1
        routes:
          keys:
            "1": en_judgment
            "2": en_judgment
          default: en_judgment
          timeout: en_no_input
          invalid: en_invalid

      - id: en_judgment
        type: info_judgment
        title: "English Menu Branch"
        rules:
          - name: "English Sales"
            variable: "User Input"
            operator: "Equal"
            value: "1"
            target: en_sales_queue
          - name: "English Service"
            variable: "User Input"
            operator: "Equal"
            value: "2"
            target: en_service_queue
        routes:
          default: en_invalid

      - id: en_sales_queue
        type: enter_queue
        title: "English Sales"
        config:
          group_name: "English Sales Team"
        routes:
          default: en_hangup

      - id: en_service_queue
        type: enter_queue
        title: "English Service"
        config:
          group_name: "English Service Team"
        routes:
          default: en_hangup

      - id: en_no_input
        type: voice_playback
        title: "EN No Input"
        audio: "EN_NoInput_MSG"
        routes:
          default: en_menu

      - id: en_invalid
        type: voice_playback
        title: "EN Invalid Option"
        audio: "EN_InvalidOption_MSG"
        routes:
          default: en_menu

      - id: en_hangup
        type: hang_up
        title: "End Call"`,

        multilang: `ivr_name: "Multi-Language Customer Service IVR"
nodes:
  - id: start_node
    type: start
    title: "Start"
    routes:
      default: welcome_node

  - id: welcome_node
    type: voice_playback
    title: "Welcome Greeting"
    audio: "Welcome_MSG_EN"
    routes:
      default: lang_menu

  - id: lang_menu
    type: collect_input
    title: "Language Menu"
    audio: "LangMenu_MSG"
    routes:
      default: lang_judgment
      timeout: no_input_node
      invalid: invalid_option_node

  - id: lang_judgment
    type: info_judgment
    title: "Language Judgment"
    rules:
      - name: "Arabic"
        variable: "User Input"
        operator: "Equal"
        value: "1"
        target: ar_main_menu
      - name: "English"
        variable: "User Input"
        operator: "Equal"
        value: "2"
        target: en_main_menu
    routes:
      default: invalid_option_node

  - id: ar_main_menu
    type: collect_input
    title: "Arabic Main Menu"
    audio: "AR_MainMenu_MSG"
    routes:
      default: ar_judgment
      timeout: ar_no_input_node
      invalid: ar_invalid_option_node

  - id: ar_judgment
    type: info_judgment
    title: "AR Service Judgment"
    rules:
      - name: "Sales"
        variable: "User Input"
        operator: "Equal"
        value: "1"
        target: ar_sales_queue
      - name: "Service"
        variable: "User Input"
        operator: "Equal"
        value: "2"
        target: ar_service_queue
    routes:
      default: ar_invalid_option_node

  - id: en_main_menu
    type: collect_input
    title: "English Main Menu"
    audio: "EN_MainMenu_MSG"
    routes:
      default: en_judgment
      timeout: en_no_input_node
      invalid: en_invalid_option_node

  - id: en_judgment
    type: info_judgment
    title: "EN Service Judgment"
    rules:
      - name: "Sales"
        variable: "User Input"
        operator: "Equal"
        value: "1"
        target: en_sales_queue
      - name: "Service"
        variable: "User Input"
        operator: "Equal"
        value: "2"
        target: en_service_queue
    routes:
      default: en_invalid_option_node

  - id: ar_sales_queue
    type: enter_queue
    title: "Arabic Sales Queue"
    config:
      group_name: "Arabic Sales"

  - id: ar_service_queue
    type: enter_queue
    title: "Arabic Service Queue"
    config:
      group_name: "Arabic Service"

  - id: en_sales_queue
    type: enter_queue
    title: "English Sales Queue"
    config:
      group_name: "English Sales"

  - id: en_service_queue
    type: enter_queue
    title: "English Service Queue"
    config:
      group_name: "English Service"

  - id: no_input_node
    type: voice_playback
    title: "No Input Notice"
    audio: "NoInput_1_MSG"
    routes:
      default: lang_menu

  - id: invalid_option_node
    type: voice_playback
    title: "Invalid Input"
    audio: "InvalidOption_MSG"
    routes:
      default: lang_menu

  - id: ar_no_input_node
    type: voice_playback
    title: "AR No Input Notice"
    audio: "AR_NoInput_MSG"
    routes:
      default: ar_main_menu

  - id: ar_invalid_option_node
    type: voice_playback
    title: "AR Invalid Input"
    audio: "AR_InvalidOption_MSG"
    routes:
      default: ar_main_menu

  - id: en_no_input_node
    type: voice_playback
    title: "EN No Input Notice"
    audio: "EN_NoInput_MSG"
    routes:
      default: en_main_menu

  - id: en_invalid_option_node
    type: voice_playback
    title: "EN Invalid Input"
    audio: "EN_InvalidOption_MSG"
    routes:
      default: en_main_menu

  - id: hangup_node
    type: hang_up
    title: "End Call"`,

        afterhours: `ivr_name: "After-Hours & RSA Routing IVR"
nodes:
  - id: start_node
    type: start
    title: "Start"
    routes:
      default: afterhours_msg

  - id: afterhours_msg
    type: collect_input
    title: "After-Hours Menu"
    audio: "AfterHours_MSG"
    routes:
      keys:
        "1": rsa_transfer
        "2": callback_confirm
      timeout: end_call

  - id: rsa_transfer
    type: voice_playback
    title: "RSA Transfer Prompt"
    audio: "AfterHours_RSA_Transfer"
    routes:
      default: end_call

  - id: callback_confirm
    type: voice_playback
    title: "Callback Confirmation"
    audio: "AfterHours_Callback_Confirm"
    routes:
      default: end_call

  - id: end_call
    type: hang_up
    title: "Hang Up"`,

        departments: `ivr_name: "Sales & Support Department IVR"
nodes:
  - id: start_node
    type: start
    title: "Start"
    routes:
      default: dept_menu

  - id: dept_menu
    type: collect_input
    title: "Main Department Menu"
    audio: "MainMenu_MSG"
    routes:
      keys:
        "1": sales_queue
        "2": support_queue
        "3": vip_queue

  - id: sales_queue
    type: enter_queue
    title: "Sales Department"
    config:
      group_name: "Sales"

  - id: support_queue
    type: enter_queue
    title: "Support Department"
    config:
      group_name: "Support"

  - id: vip_queue
    type: enter_queue
    title: "VIP Account Queue"
    config:
      group_name: "VIP Support"`,

        blank: `ivr_name: "New Blank IVR Flow"
nodes:
  - id: start_node
    type: start
    title: "Start"
    routes:
      default: welcome_node

  - id: welcome_node
    type: voice_playback
    title: "Welcome Voice"
    audio: "Welcome_MSG"`
    };

    if (ivrTemplateSelect && ivrYamlInput) {
        const loadSelectedTemplate = () => {
            const key = ivrTemplateSelect.value;
            if (IVR_TEMPLATES[key]) {
                ivrYamlInput.value = IVR_TEMPLATES[key];
                ivrYamlInput.dispatchEvent(new Event('input', { bubbles: true }));
                localStorage.setItem('saved_state_ivr-yaml-input', ivrYamlInput.value);
                logToConsole(`Loaded template: ${ivrTemplateSelect.options[ivrTemplateSelect.selectedIndex].text}`, 'system');
                validateIvrContent(false);
            }
        };

        if (btnLoadIvrTemplate) {
            btnLoadIvrTemplate.addEventListener('click', loadSelectedTemplate);
        }
        ivrTemplateSelect.addEventListener('change', loadSelectedTemplate);

        function syncTemplateSelectToContent() {
            const val = (ivrYamlInput.value || '').trim();
            if (val.includes('canvases:')) {
                ivrTemplateSelect.value = 'multilang_multicanvas';
            } else if (val.includes('After-Hours & RSA')) {
                ivrTemplateSelect.value = 'afterhours';
            } else if (val.includes('Sales & Service Branching')) {
                ivrTemplateSelect.value = 'departments';
            } else if (val.includes('New Blank IVR Flow')) {
                ivrTemplateSelect.value = 'blank';
            } else if (val.includes('nodes:')) {
                ivrTemplateSelect.value = 'multilang';
            }
        }

        // Set default template if input is currently empty
        if (!(ivrYamlInput.value || '').trim()) {
            ivrYamlInput.value = IVR_TEMPLATES.multilang_multicanvas;
            ivrYamlInput.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            syncTemplateSelectToContent();
        }
    }

    // Modal Close Handlers
    if (btnClosePairModal && modalPairIvrTabs) {
        btnClosePairModal.addEventListener('click', () => {
            modalPairIvrTabs.style.display = 'none';
        });
    }
    if (btnCancelPairModal && modalPairIvrTabs) {
        btnCancelPairModal.addEventListener('click', () => {
            modalPairIvrTabs.style.display = 'none';
        });
    }
    if (modalPairIvrTabs) {
        modalPairIvrTabs.addEventListener('click', (e) => {
            if (e.target === modalPairIvrTabs) {
                modalPairIvrTabs.style.display = 'none';
            }
        });
    }

    async function validateIvrContent(logSuccess = true) {
        const content = ivrYamlInput ? ivrYamlInput.value.trim() : '';
        if (!content) {
            if (ivrValidBadge) {
                ivrValidBadge.textContent = 'Empty';
                ivrValidBadge.style.color = '#f59e0b';
            }
            if (ivrCanvasCount) ivrCanvasCount.style.display = 'none';
            lastValidatedIvrData = null;
            return false;
        }

        try {
            const res = await fetch('/api/validate-ivr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workflow_content: content })
            });
            const json = await res.json();
            if (json.success && json.data && json.data.valid) {
                lastValidatedIvrData = json.data;
                const summary = json.data.summary;
                if (ivrValidBadge) {
                    ivrValidBadge.textContent = 'Valid Schema';
                    ivrValidBadge.style.color = '#00ffaa';
                    ivrValidBadge.style.background = 'rgba(0, 255, 170, 0.1)';
                    ivrValidBadge.style.borderColor = 'rgba(0, 255, 170, 0.2)';
                }
                if (ivrCanvasCount) {
                    if (json.data.is_multi_canvas) {
                        ivrCanvasCount.textContent = `${json.data.canvases_count} Canvases`;
                        ivrCanvasCount.style.display = 'inline-block';
                    } else {
                        ivrCanvasCount.style.display = 'none';
                    }
                }
                if (ivrNodeCount) ivrNodeCount.textContent = `${summary.total_nodes} Nodes`;
                if (ivrRouteCount) ivrRouteCount.textContent = `${summary.total_routes} Routes`;

                if (logSuccess) {
                    const canvasInfo = json.data.is_multi_canvas ? `across ${json.data.canvases_count} canvases ` : '';
                    logToConsole(`[IVR VALID] '${json.data.ivr_name}' is valid! Total: ${summary.total_nodes} nodes ${canvasInfo}and ${summary.total_routes} routes. Referenced voices: ${json.data.referenced_voices.join(', ') || 'None'}`, 'success');
                }
                return true;
            } else {
                lastValidatedIvrData = null;
                if (ivrValidBadge) {
                    ivrValidBadge.textContent = 'Invalid Schema';
                    ivrValidBadge.style.color = '#ff4444';
                    ivrValidBadge.style.background = 'rgba(255, 68, 68, 0.1)';
                    ivrValidBadge.style.borderColor = 'rgba(255, 68, 68, 0.2)';
                }
                if (ivrCanvasCount) ivrCanvasCount.style.display = 'none';
                logToConsole(`[IVR ERROR] ${json.message || 'Validation failed'}`, 'error');
                return false;
            }
        } catch (e) {
            lastValidatedIvrData = null;
            if (ivrValidBadge) {
                ivrValidBadge.textContent = 'Error';
                ivrValidBadge.style.color = '#ff4444';
            }
            if (ivrCanvasCount) ivrCanvasCount.style.display = 'none';
            logToConsole(`[IVR ERROR] Request error: ${e.message}`, 'error');
            return false;
        }
    }

    if (btnValidateIvr) {
        btnValidateIvr.addEventListener('click', () => validateIvrContent(true));
    }

    let isBuildingIvr = false;
    let ivrAbortController = null;

    function updateDuplicateWarning() {
        if (!ivrTabPairingList) return;
        const selects = ivrTabPairingList.querySelectorAll('.canvas-pair-select');
        const seen = new Set();
        let hasDuplicate = false;
        selects.forEach(sel => {
            const val = sel.value;
            if (seen.has(val)) {
                hasDuplicate = true;
            }
            seen.add(val);
        });

        if (ivrPairDuplicateWarning) {
            ivrPairDuplicateWarning.style.display = (hasDuplicate && selects.length > 1) ? 'block' : 'none';
        }
        if (btnConfirmPairBuild) {
            btnConfirmPairBuild.disabled = (hasDuplicate && selects.length > 1);
            if (hasDuplicate && selects.length > 1) {
                btnConfirmPairBuild.style.opacity = '0.5';
                btnConfirmPairBuild.style.cursor = 'not-allowed';
            } else {
                btnConfirmPairBuild.style.opacity = '1';
                btnConfirmPairBuild.style.cursor = 'pointer';
            }
        }
    }

    function renderTabPairingModal(canvases, detectedTabs) {
        if (!ivrTabPairingList) return;
        ivrTabPairingList.innerHTML = '';

        if (ivrPairTabsWarning) {
            if (detectedTabs.length < canvases.length) {
                ivrPairTabsWarning.style.display = 'block';
                ivrPairTabsWarning.innerHTML = `⚠️ <strong>Notice:</strong> Found ${detectedTabs.length} open IVR tab(s), but workflow requires ${canvases.length} canvases. Please open ${canvases.length - detectedTabs.length} more tab(s) in Chrome and click <strong>"🔄 Refresh Tabs"</strong> above.`;
            } else {
                ivrPairTabsWarning.style.display = 'none';
            }
        }

        canvases.forEach((c, cIdx) => {
            const row = document.createElement('div');
            row.className = 'canvas-pair-card';

            const nodeCount = c.summary ? c.summary.total_nodes : (c.nodes ? c.nodes.length : 0);
            const routeCount = c.summary ? c.summary.total_routes : 0;

            const infoDiv = document.createElement('div');
            infoDiv.className = 'canvas-pair-info';
            infoDiv.innerHTML = `
                <div class="canvas-pair-name" title="${c.canvas_name}">📌 Canvas ${cIdx + 1}: ${c.canvas_name}</div>
                <div class="canvas-pair-meta">${nodeCount} Nodes, ${routeCount} Routes</div>
            `;

            const selDiv = document.createElement('div');
            selDiv.className = 'canvas-pair-selector';

            const select = document.createElement('select');
            select.className = 'canvas-pair-select';
            select.dataset.canvasIndex = cIdx;

            if (detectedTabs.length > 0) {
                detectedTabs.forEach((tab, tIdx) => {
                    const opt = document.createElement('option');
                    opt.value = tab.index;
                    opt.textContent = `Tab ${tab.tab_number || (tIdx + 1)}: ${tab.flow_name || tab.title}`;
                    select.appendChild(opt);
                });
                // Pre-match canvas index to tab index if available
                if (cIdx < detectedTabs.length) {
                    select.value = detectedTabs[cIdx].index;
                } else {
                    select.value = detectedTabs[0].index;
                }
            } else {
                const opt = document.createElement('option');
                opt.value = cIdx;
                opt.textContent = `Chrome Tab ${cIdx + 1} (Active Window)`;
                select.appendChild(opt);
            }

            select.addEventListener('change', updateDuplicateWarning);

            selDiv.appendChild(select);
            row.appendChild(infoDiv);
            row.appendChild(selDiv);
            ivrTabPairingList.appendChild(row);
        });

        updateDuplicateWarning();
    }

    if (btnRefreshPairTabs) {
        btnRefreshPairTabs.addEventListener('click', async () => {
            if (!lastValidatedIvrData || !Array.isArray(lastValidatedIvrData.canvases)) return;
            btnRefreshPairTabs.disabled = true;
            btnRefreshPairTabs.textContent = 'Refreshing...';
            const cdpPort = ivrCdpPort ? parseInt(ivrCdpPort.value, 10) || 9225 : 9225;
            const cdpUrl = ivrCdpUrl ? ivrCdpUrl.value.trim() : '';
            try {
                const tabRes = await fetch('/api/list-ivr-tabs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cdp_port: cdpPort, cdp_url: cdpUrl })
                });
                const tabData = await tabRes.json();
                const detected = (tabData.success && Array.isArray(tabData.tabs)) ? tabData.tabs : [];
                renderTabPairingModal(lastValidatedIvrData.canvases, detected);
                logToConsole(`Scanned Chrome tabs: Found ${detected.length} canvas tab(s).`, 'system');
            } catch (e) {
                console.warn('Error refreshing tabs:', e);
            } finally {
                btnRefreshPairTabs.disabled = false;
                btnRefreshPairTabs.textContent = '🔄 Refresh Tabs';
            }
        });
    }

    async function startIvrBuild(content, cdpPort, cdpUrl, authScript, tabMappings = null) {
        isBuildingIvr = true;
        ivrAbortController = new AbortController();

        btnBuildIvr.classList.add('btn-danger');
        btnBuildIvr.textContent = 'Stop Build';
        btnBuildIvr.disabled = false;
        logToConsole(`Starting automated IVR canvas build on CDP port ${cdpPort}...`, 'system');

        try {
            const res = await fetch('/api/build-ivr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: ivrAbortController.signal,
                body: JSON.stringify({
                    workflow_content: content,
                    cdp_port: cdpPort,
                    cdp_url: cdpUrl,
                    auth_script: authScript,
                    tab_mappings: tabMappings
                })
            });

            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        let type = 'system';
                        if (data.status === 'error') type = 'error';
                        else if (data.status === 'done') type = 'success';
                        else if (data.status === 'warn') type = 'error';
                        else if (data.status === 'progress') type = 'voice-active';

                        logToConsole(data.message, type);
                    } catch (e) {
                        logToConsole(line, 'system');
                    }
                }
            }
        } catch (err) {
            if (err.name === 'AbortError') {
                logToConsole('IVR Build aborted by user.', 'system');
            } else {
                logToConsole(`IVR Build request failed: ${err.message}`, 'error');
            }
        } finally {
            isBuildingIvr = false;
            ivrAbortController = null;
            btnBuildIvr.classList.remove('btn-danger');
            btnBuildIvr.disabled = false;
            btnBuildIvr.textContent = 'Build on Canvas';
        }
    }

    if (btnConfirmPairBuild && modalPairIvrTabs) {
        btnConfirmPairBuild.addEventListener('click', () => {
            const content = ivrYamlInput ? ivrYamlInput.value.trim() : '';
            const cdpPort = ivrCdpPort ? parseInt(ivrCdpPort.value, 10) || 9225 : 9225;
            const cdpUrl = ivrCdpUrl ? ivrCdpUrl.value.trim() : '';
            const globalAuthTextarea = document.getElementById('global-auth-script');
            const authScript = globalAuthTextarea ? globalAuthTextarea.value.trim() : '';

            const mappings = [];
            const seenTabs = new Set();
            let hasDuplicate = false;
            const selects = ivrTabPairingList.querySelectorAll('.canvas-pair-select');
            selects.forEach((sel, cIdx) => {
                const tabIdx = parseInt(sel.value, 10) || 0;
                if (seenTabs.has(tabIdx)) {
                    hasDuplicate = true;
                }
                seenTabs.add(tabIdx);
                mappings.push({
                    canvas_index: parseInt(sel.dataset.canvasIndex || cIdx, 10),
                    tab_index: tabIdx
                });
            });

            if (hasDuplicate && mappings.length > 1) {
                logToConsole('Cannot build: Multiple canvases are mapped to the same Chrome tab. Please map each canvas to a distinct tab.', 'error');
                if (ivrPairDuplicateWarning) ivrPairDuplicateWarning.style.display = 'block';
                return;
            }

            modalPairIvrTabs.style.display = 'none';
            startIvrBuild(content, cdpPort, cdpUrl, authScript, mappings);
        });
    }

    if (btnBuildIvr) {
        btnBuildIvr.addEventListener('click', async () => {
            if (isBuildingIvr) {
                // User clicked "Stop Build"
                btnBuildIvr.disabled = true;
                btnBuildIvr.textContent = 'Stopping...';
                logToConsole('Stop signal sent to IVR builder...', 'warn');

                // 1. Immediately abort the client-side streaming reader
                if (ivrAbortController) {
                    try {
                        ivrAbortController.abort();
                    } catch (_) { }
                }

                // 2. Notify backend server to immediately signal the worker thread
                fetch('/api/stop-ivr', { method: 'POST' }).catch(err => {
                    console.warn('Backend stop notification error:', err);
                });

                // 3. Fallback safety reset in case stream reader was already closed
                setTimeout(() => {
                    if (isBuildingIvr) {
                        isBuildingIvr = false;
                        ivrAbortController = null;
                        btnBuildIvr.classList.remove('btn-danger');
                        btnBuildIvr.disabled = false;
                        btnBuildIvr.textContent = 'Build on Canvas';
                    }
                }, 600);
                return;
            }

            const content = ivrYamlInput ? ivrYamlInput.value.trim() : '';
            if (!content) {
                logToConsole('Please enter or load an IVR workflow definition before building.', 'error');
                return;
            }

            const isValid = await validateIvrContent(false);
            if (!isValid || !lastValidatedIvrData) {
                logToConsole('Cannot build: IVR Workflow has validation errors. Fix errors above.', 'error');
                return;
            }

            const cdpPort = ivrCdpPort ? parseInt(ivrCdpPort.value, 10) || 9225 : 9225;
            const cdpUrl = ivrCdpUrl ? ivrCdpUrl.value.trim() : '';
            const globalAuthTextarea = document.getElementById('global-auth-script');
            const authScript = globalAuthTextarea ? globalAuthTextarea.value.trim() : '';

            // If Multi-Canvas: intercept and present Tab Pairing Modal
            if (lastValidatedIvrData.is_multi_canvas && Array.isArray(lastValidatedIvrData.canvases)) {
                logToConsole('Querying active Chrome tabs for Multi-Canvas build...', 'system');
                btnBuildIvr.disabled = true;
                btnBuildIvr.textContent = 'Detecting Tabs...';

                let detectedTabs = [];
                try {
                    const tabRes = await fetch('/api/list-ivr-tabs', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cdp_port: cdpPort, cdp_url: cdpUrl })
                    });
                    const tabData = await tabRes.json();
                    if (tabData.success && Array.isArray(tabData.tabs)) {
                        detectedTabs = tabData.tabs;
                    }
                } catch (e) {
                    console.warn('Failed to query active tabs:', e);
                } finally {
                    btnBuildIvr.disabled = false;
                    btnBuildIvr.textContent = 'Build on Canvas';
                }

                renderTabPairingModal(lastValidatedIvrData.canvases, detectedTabs);
                if (modalPairIvrTabs) modalPairIvrTabs.style.display = 'flex';
                return;
            }

            // Classic Single Canvas build
            startIvrBuild(content, cdpPort, cdpUrl, authScript, null);
        });
    }

    // Initialize TenantProfileManager after all modules, elements, and event listeners are fully defined
    TenantProfileManager.init();

    window.addEventListener('beforeunload', () => {
        TenantProfileManager.syncCurrentDomToProfile();
    });

    // Auto-validate on page load
    setTimeout(() => {
        validateIvrContent(false);
    }, 600);
});
