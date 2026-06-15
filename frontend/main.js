/* hostpanel-package-php - frontend/main.js */
(function () {
  'use strict';

  const sdk = window.__hpkg_sdk;
  const { html, useEffect, useState, useCallback } = sdk;
  const { SdkConfirmModal, SdkDataTable } = sdk.components;
  const { useToast } = sdk.hooks;

  const SIZE_OPTIONS = ['32M', '64M', '128M', '256M', '512M', '1G', '2G'];

  function PhpFormModal({ title, mode, assignment, domains, onClose, onSubmit }) {
    const firstDomain = assignment?.domain || domains[0]?.domain || '';
    const selectedInitial = domains.find(item => item.domain === firstDomain);
    const [domain, setDomain] = useState(firstDomain);
    const [documentRoot, setDocumentRoot] = useState(assignment?.document_root || selectedInitial?.document_root || '');
    const [memoryLimit, setMemoryLimit] = useState(assignment?.memory_limit || '256M');
    const [uploadMaxFilesize, setUploadMaxFilesize] = useState(assignment?.upload_max_filesize || '64M');
    const [postMaxSize, setPostMaxSize] = useState(assignment?.post_max_size || '64M');
    const [maxExecutionTime, setMaxExecutionTime] = useState(assignment?.max_execution_time || 60);
    const [maxInputVars, setMaxInputVars] = useState(assignment?.max_input_vars || 3000);
    const [displayErrors, setDisplayErrors] = useState(Boolean(assignment?.display_errors));
    const [busy, setBusy] = useState(false);
    const [formError, setFormError] = useState('');

    const selectDomain = value => {
      setDomain(value);
      const selected = domains.find(item => item.domain === value);
      if (selected) setDocumentRoot(selected.document_root || '');
    };

    const sizeSelect = (label, value, setValue) => html`
      <div class="field">
        <label>${label}</label>
        <select value=${value} onChange=${e => setValue(e.target.value)}>
          ${SIZE_OPTIONS.map(item => html`<option value=${item}>${item}</option>`)}
        </select>
      </div>
    `;

    const save = async () => {
      setFormError('');
      if (mode === 'create' && !domain) {
        setFormError('Target domain is required');
        return;
      }
      setBusy(true);
      try {
        await onSubmit({
          domain,
          memory_limit: memoryLimit,
          upload_max_filesize: uploadMaxFilesize,
          post_max_size: postMaxSize,
          max_execution_time: Number(maxExecutionTime),
          max_input_vars: Number(maxInputVars),
          display_errors: displayErrors,
        });
      } catch (e) {
        setFormError(e.message || 'Something went wrong');
      } finally {
        setBusy(false);
      }
    };

    return html`
      <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && onClose()}>
        <div class="modal animate-fade-in" style=${{ width: 680, maxWidth: 'calc(100vw - 32px)' }}>
          <div class="modal-header">
            <span class="modal-title">${title}</span>
            <button class="modal-close" onClick=${onClose} aria-label="Close">x</button>
          </div>
          <div class="modal-body" style=${{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            ${mode === 'create' && html`
              <div class="field">
                <label>Target domain</label>
                <select value=${domain} onChange=${e => selectDomain(e.target.value)}>
                  ${domains.map(item => html`
                    <option value=${item.domain}>${item.domain}</option>
                  `)}
                </select>
              </div>
            `}
            <div class="field">
              <label>Runtime</label>
              <input type="text" value="PHP 8.4" disabled=${true} />
            </div>
            <div class="field" style=${{ gridColumn: '1 / -1' }}>
              <label>Document root</label>
              <input type="text" value=${documentRoot} disabled=${true} />
            </div>
            ${sizeSelect('Memory limit', memoryLimit, setMemoryLimit)}
            ${sizeSelect('Upload max filesize', uploadMaxFilesize, setUploadMaxFilesize)}
            ${sizeSelect('Post max size', postMaxSize, setPostMaxSize)}
            <div class="field">
              <label>Max execution time</label>
              <input type="number" min="10" max="300" value=${maxExecutionTime} onInput=${e => setMaxExecutionTime(e.target.value)} />
            </div>
            <div class="field">
              <label>Max input vars</label>
              <input type="number" min="1000" max="10000" value=${maxInputVars} onInput=${e => setMaxInputVars(e.target.value)} />
            </div>
            <div class="field" style=${{ justifyContent: 'end' }}>
              <label>Display errors</label>
              <label style=${{ display: 'flex', alignItems: 'center', gap: 8, height: 38 }}>
                <input type="checkbox" checked=${displayErrors} onChange=${e => setDisplayErrors(e.target.checked)} />
                <span>${displayErrors ? 'On' : 'Off'}</span>
              </label>
            </div>
            ${formError && html`
              <div style=${{ gridColumn: '1 / -1', color: 'var(--err)', fontSize: 12 }}>${formError}</div>
            `}
          </div>
          <div class="modal-footer">
            <button class="btn btn-ghost btn-sm" onClick=${onClose} disabled=${busy}>Cancel</button>
            <button class="btn btn-primary btn-sm" onClick=${save} disabled=${busy}>
              ${busy ? 'Working...' : (mode === 'create' ? 'Enable PHP' : 'Save')}
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function LogsModal({ assignment, onClose }) {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(() => {
      setLoading(true);
      sdk.fetch('GET', '/cpanelapi/php/assignments/' + encodeURIComponent(assignment.id) + '/logs')
        .then(data => setLogs(data || []))
        .finally(() => setLoading(false));
    }, [assignment.id]);

    useEffect(() => { load(); }, [load]);

    return html`
      <div class="modal-overlay" onClick=${e => e.target === e.currentTarget && onClose()}>
        <div class="modal animate-fade-in" style=${{ width: 760, maxWidth: 'calc(100vw - 32px)' }}>
          <div class="modal-header">
            <span class="modal-title">${'Logs - ' + assignment.domain}</span>
            <button class="modal-close" onClick=${onClose} aria-label="Close">x</button>
          </div>
          <div class="modal-body">
            <pre class="log-output" style=${{ minHeight: 320, maxHeight: 460, overflow: 'auto' }}>
${loading ? 'Loading...' : (logs.map(row => `${row.created_at || ''} ${row.level || ''} ${row.message || ''}`).join('\n') || 'No logs yet')}
            </pre>
          </div>
          <div class="modal-footer">
            <button class="btn btn-ghost btn-sm" onClick=${load}>Refresh</button>
            <button class="btn btn-primary btn-sm" onClick=${onClose}>Close</button>
          </div>
        </div>
      </div>
    `;
  }

  function PhpPlugin() {
    const { ok } = useToast();
    const [assignments, setAssignments] = useState([]);
    const [domains, setDomains] = useState([]);
    const [runtime, setRuntime] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [createOpen, setCreateOpen] = useState(false);
    const [editTarget, setEditTarget] = useState(null);
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [logsTarget, setLogsTarget] = useState(null);

    const load = useCallback(() => {
      setLoading(true);
      setError('');
      Promise.all([
        sdk.fetch('GET', '/cpanelapi/php/assignments'),
        sdk.fetch('GET', '/cpanelapi/php/domains'),
        sdk.fetch('GET', '/cpanelapi/php/runtime'),
      ])
        .then(([assignmentData, domainData, runtimeData]) => {
          setAssignments(assignmentData || []);
          setDomains(domainData || []);
          setRuntime(runtimeData || {});
        })
        .catch(e => setError(e.message || 'Failed to load PHP sites'))
        .finally(() => setLoading(false));
    }, []);

    useEffect(() => { load(); }, [load]);

    const createAssignment = async values => {
      await sdk.fetch('POST', '/cpanelapi/php/assignments', values);
      setCreateOpen(false);
      ok('PHP enabled');
      load();
    };

    const updateAssignment = async values => {
      await sdk.fetch('PUT', '/cpanelapi/php/assignments/' + encodeURIComponent(editTarget.id), {
        memory_limit: values.memory_limit,
        upload_max_filesize: values.upload_max_filesize,
        post_max_size: values.post_max_size,
        max_execution_time: values.max_execution_time,
        max_input_vars: values.max_input_vars,
        display_errors: values.display_errors,
      });
      setEditTarget(null);
      ok('PHP settings updated');
      load();
    };

    const restart = async assignment => {
      await sdk.fetch('POST', '/cpanelapi/php/assignments/' + encodeURIComponent(assignment.id) + '/restart');
      ok('PHP-FPM restarted');
      load();
    };

    const deleteAssignment = async () => {
      await sdk.fetch('DELETE', '/cpanelapi/php/assignments/' + encodeURIComponent(deleteTarget.id));
      setDeleteTarget(null);
      ok('PHP disabled');
      load();
    };

    return html`
      <div class="page">
        <div class="page-header">
          <div>
            <h1 class="page-title">PHP</h1>
            <p class="page-desc">Manage PHP for hosted sites</p>
          </div>
        </div>

        <div class="card" style=${{ marginBottom: 16 }}>
          <div style=${{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
            <div>
              <div style=${{ fontSize: 11, color: 'var(--muted)' }}>php</div>
              <div style=${{ fontFamily: 'monospace', fontSize: 13 }}>${runtime.php || '-'}</div>
            </div>
            <div>
              <div style=${{ fontSize: 11, color: 'var(--muted)' }}>php-fpm</div>
              <div style=${{ fontFamily: 'monospace', fontSize: 13 }}>${runtime.php_fpm || '-'}</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div style=${{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
            <span class="card-title" style=${{ marginBottom: 0 }}>Sites</span>
            <button class="btn btn-primary btn-sm" onClick=${() => setCreateOpen(true)} disabled=${!domains.length}>
              Enable PHP
            </button>
          </div>

          ${error
            ? html`
                <div class="empty">
                  <div class="empty-title" style=${{ color: 'var(--err)' }}>Could not load PHP sites</div>
                  <div class="empty-desc">${error}</div>
                </div>
              `
            : html`
                <${SdkDataTable}
                  columns=${[
                    { key: 'domain', label: 'Domain' },
                    { key: 'username', label: 'Owner', type: 'mono' },
                    { key: 'php_version', label: 'Runtime' },
                    { key: 'document_root', label: 'Document Root', type: 'mono' },
                    { key: 'status', label: 'Status' },
                  ]}
                  rows=${assignments}
                  loading=${loading}
                  empty=${{ title: 'No PHP sites', desc: 'Enable PHP for an existing domain or subdomain.' }}
                  renderActions=${row => html`
                    <button class="btn btn-ghost btn-sm" onClick=${() => restart(row)}>Restart</button>
                    <button class="btn btn-ghost btn-sm" onClick=${() => setLogsTarget(row)}>Logs</button>
                    <button class="btn btn-ghost btn-sm" onClick=${() => setEditTarget(row)}>Edit</button>
                    <button class="btn btn-danger btn-sm" onClick=${() => setDeleteTarget(row)}>Disable</button>
                  `}
                />
              `
          }
        </div>
      </div>

      ${createOpen && html`
        <${PhpFormModal}
          title="Enable PHP"
          mode="create"
          domains=${domains}
          onClose=${() => setCreateOpen(false)}
          onSubmit=${createAssignment}
        />
      `}

      ${editTarget && html`
        <${PhpFormModal}
          title=${'Edit PHP - ' + editTarget.domain}
          mode="edit"
          assignment=${editTarget}
          domains=${domains}
          onClose=${() => setEditTarget(null)}
          onSubmit=${updateAssignment}
        />
      `}

      ${logsTarget && html`
        <${LogsModal} assignment=${logsTarget} onClose=${() => setLogsTarget(null)} />
      `}

      ${deleteTarget && html`
        <${SdkConfirmModal}
          open=${true}
          title="Disable PHP"
          message=${'Disable PHP for "' + deleteTarget.domain + '"? Website files are preserved.'}
          danger=${true}
          onClose=${() => setDeleteTarget(null)}
          onConfirm=${deleteAssignment}
        />
      `}
    `;
  }

  sdk.register('php', PhpPlugin);
})();
