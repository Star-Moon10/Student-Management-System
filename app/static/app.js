const state = { user: null, students: [], selectedStudentIds: new Set(), selectedRelatedCandidateIds: new Set(), studentPage: 1, studentPageSize: 50, studentTotalPages: 1, currentStudent: null, administrators: [], currentAdministrator: null, savedStudentFilters: [], activeView: 'dashboard', aiConversationId: null, aiSuggestionRequest: 0, highRiskApproval: null, excelPreview: null, importTemplates: [], exportTemplates: [], pendingExport: null, importReportCache: {}, importReportHideTimer: null, importReportTrigger: null, passwordPrompted: false, idleLogoutTimer: null, idleLogoutStarted: false, lastActivityAt: 0, dataScopePreviewTimer: null, dataScopePreviewRequest: 0, latestSystemUpdate: null, systemUpdateTimer: null };
const IDLE_LOGOUT_TIMEOUT_MS = 5 * 60 * 1000;
const titles = {
  dashboard: ['工作台', '概览'],
  students: ['学生管理', '学生档案'],
  imports: ['数据管理', '数据导入'],
  candidates: ['数据管理', '学生相关信息导入审核'],
  reports: ['数据管理', '导出记录'],
  operations: ['系统管理', '质量与运维'],
  settings: ['系统管理', '系统设置'],
  manual: ['帮助中心', '系统操作手册'],
  'admin-help': ['帮助中心', '管理员帮助'],
  audit: ['系统管理', '审计与 AI 记录'],
};

function csrfToken() {
  return document.cookie.split('; ').find((item) => item.startsWith('csrf_token='))?.split('=').slice(1).join('') || '';
}

function cookieValue(name) {
  return document.cookie.split('; ').find((item) => item.startsWith(`${name}=`))?.split('=').slice(1).join('') || '';
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && !['GET', 'HEAD'].includes(options.method.toUpperCase())) headers.set('X-CSRF-Token', csrfToken());
  const response = await fetch(path, {...options, headers});
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    window.location.assign('/login');
    throw new Error('登录已失效');
  }
  if (!response.ok) throw new Error(payload.detail || '操作失败，请稍后重试。');
  return payload;
}

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function dateTime(value) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('zh-CN', {dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Shanghai'}).format(new Date(value));
}

function statusTag(value) {
  const map = {
    active: ['在读', 'success'], inactive: ['非在读', 'muted'], completed: ['完成', 'success'],
    completed_with_errors: ['部分完成', 'pending'], processing: ['处理中', 'pending'], failed: ['失败', 'error'],
  };
  const [label, style] = map[value] || [value || '-', 'muted'];
  return `<span class="status ${style}">${escapeHTML(label)}</span>`;
}

let toastTimer;
function toast(message, isError = false) {
  const node = document.querySelector('#toast');
  node.textContent = message;
  node.classList.toggle('error', isError);
  node.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove('show'), 3600);
}

function refreshIcons() { window.lucide?.createIcons(); }

function hasCapability(capability) {
  return Boolean(state.user?.role === 'super_admin' || (state.user?.capabilities || []).includes(capability));
}

function isMobileViewport() {
  return window.matchMedia('(max-width: 800px)').matches;
}

function setAssistantOpen(open, focusInput = true) {
  const shell = document.querySelector('.app-shell');
  const launcher = document.querySelector('#assistant-launch');
  const mobile = isMobileViewport();
  shell.classList.toggle('assistant-open', mobile && open);
  shell.classList.toggle('assistant-collapsed', !mobile && !open);
  if (mobile) shell.classList.remove('menu-open');
  document.body.classList.toggle('mobile-assistant-open', mobile && open);
  launcher.setAttribute('aria-expanded', String(open));
  if (open && focusInput) {
    window.setTimeout(() => document.querySelector('#ai-question').focus(), 220);
  } else if (!open) {
    launcher.focus();
  }
}

function syncAssistantLayout() {
  const shell = document.querySelector('.app-shell');
  const launcher = document.querySelector('#assistant-launch');
  if (isMobileViewport()) {
    shell.classList.remove('assistant-collapsed', 'assistant-open', 'menu-open');
    document.body.classList.remove('mobile-assistant-open');
    launcher.setAttribute('aria-expanded', 'false');
    return;
  }
  shell.classList.remove('assistant-open', 'menu-open');
  document.body.classList.remove('mobile-assistant-open');
  launcher.setAttribute('aria-expanded', String(!shell.classList.contains('assistant-collapsed')));
}

function setView(view) {
  if (['manual', 'admin-help'].includes(view) && state.user?.role === 'super_admin') {
    toast('超级管理员不需要查看此帮助页面。', true);
    return;
  }
  if (view === 'audit' && (!['super_admin', 'admin'].includes(state.user?.role) || !hasCapability('audit_view'))) {
    toast('只有超级管理员和普通管理员可以查看审计与 AI 记录。', true);
    return;
  }
  if (view === 'operations' && (!['super_admin', 'admin'].includes(state.user?.role) || (!hasCapability('quality_manage') && !hasCapability('source_manage')))) { toast('没有质量与运维查看权限。', true); return; }
  if (view === 'settings' && !['super_admin', 'admin'].includes(state.user?.role)) {
    toast('只有管理员可以进入系统设置。', true);
    return;
  }
  if (view === 'candidates' && !hasCapability('related_review')) {
    toast('没有学生相关信息审核权限。', true);
    return;
  }
  if (view === 'admin-help' && !['super_admin', 'admin'].includes(state.user?.role)) {
    toast('只有管理员可以查看管理员帮助。', true);
    return;
  }
  state.activeView = view;
  hideImportReportPreview();
  const [eyebrow, title] = titles[view];
  document.querySelector('#view-eyebrow').textContent = eyebrow;
  document.querySelector('#view-title').textContent = title;
  document.querySelectorAll('.view').forEach((node) => node.classList.toggle('active', node.id === `view-${view}`));
  document.querySelectorAll('.nav-item').forEach((node) => node.classList.toggle('active', node.dataset.view === view));
  document.querySelector('.app-shell').classList.remove('menu-open');
  if (view === 'students') Promise.all([loadStudentFilterOptions(), loadSavedStudentFilters()]).then(loadStudents).catch((errorObject) => toast(errorObject.message, true));
  if (view === 'imports') loadImports();
  if (view === 'candidates') loadCandidates();
  if (view === 'reports') loadExportTemplates().catch((errorObject) => toast(errorObject.message, true));
  if (view === 'settings') loadSystemSettings();
  if (view === 'audit') loadAuditView();
  if (view === 'operations') loadOperations();
  refreshIcons();
}

async function loadUser() {
  const user = await api('/api/me');
  state.user = user;
  document.querySelector('#user-name').textContent = user.display_name || user.username;
  document.querySelector('#user-avatar').textContent = (user.display_name || user.username).slice(0, 1);
  const mayEdit = hasCapability('student_edit');
  document.querySelectorAll('.edit-only').forEach((node) => { node.hidden = !mayEdit; });
  document.querySelectorAll('.export-only').forEach((node) => { node.hidden = !hasCapability('student_export'); });
  document.querySelectorAll('.related-review-only').forEach((node) => { node.hidden = !hasCapability('related_review'); });
  document.querySelector('[data-view="candidates"]').hidden = !hasCapability('related_review');
  document.querySelector('#system-settings-nav').hidden = !['super_admin', 'admin'].includes(user.role);
  if (user.role === 'super_admin') {
    document.querySelector('#dashboard-help-card')?.remove();
    document.querySelector('#dashboard-admin-help-card')?.remove();
    document.querySelector('#view-manual')?.remove();
    document.querySelector('#view-admin-help')?.remove();
  } else {
    const manualCard = document.querySelector('#dashboard-help-card');
    const adminHelpCard = document.querySelector('#dashboard-admin-help-card');
    if (manualCard) manualCard.hidden = false;
    if (adminHelpCard) adminHelpCard.hidden = user.role !== 'admin';
  }
  document.querySelector('#high-risk-settings-section').hidden = user.role !== 'super_admin';
  document.querySelector('#audit-nav').hidden = !['super_admin', 'admin'].includes(user.role) || !hasCapability('audit_view');
  document.querySelector('#operations-nav').hidden = !['super_admin', 'admin'].includes(user.role) || (!hasCapability('quality_manage') && !hasCapability('source_manage'));
  document.querySelector('#nav-system-label').hidden = document.querySelector('#operations-nav').hidden && document.querySelector('#system-settings-nav').hidden && document.querySelector('#audit-nav').hidden;
  const visibleViews = {
    operations: !document.querySelector('#operations-nav').hidden,
    settings: !document.querySelector('#system-settings-nav').hidden,
    audit: !document.querySelector('#audit-nav').hidden,
    'admin-help': user.role === 'admin',
  };
  Object.entries(visibleViews).forEach(([view, visible]) => {
    const viewNode = document.querySelector(`#view-${view}`);
    if (viewNode) viewNode.hidden = !visible;
  });
  document.querySelectorAll('[data-go-view]').forEach((node) => {
    const targetView = node.dataset.goView;
    if (targetView in visibleViews) node.hidden = !visibleViews[targetView];
  });
  if (user.must_change_password && !state.passwordPrompted) {
    state.passwordPrompted = true;
    window.setTimeout(() => openAccountSecurityDialog(true), 0);
  }
}

async function loadAiStatus() {
  const statusNode = document.querySelector('#assistant-status');
  const label = document.querySelector('#assistant-status-label');
  try {
    const data = await api('/api/ai/status');
    statusNode.classList.toggle('degraded', !data.available);
    label.textContent = data.available ? '可用' : '服务降级';
    statusNode.title = data.detail || '';
  } catch (_) {
    statusNode.classList.add('degraded');
    label.textContent = '服务降级';
    statusNode.title = '本地模型服务不可用';
  }
}

async function loadDashboard() {
  const data = await api('/api/dashboard');
  document.querySelector('#metric-total').textContent = data.metrics.total_students;
  document.querySelector('#metric-active').textContent = data.metrics.contactable_students;
  document.querySelector('#metric-imports').textContent = data.metrics.import_batches;
  document.querySelector('#metric-pending').textContent = data.metrics.pending_candidates;
  document.querySelector('#candidate-count').textContent = data.metrics.pending_candidates;
  const body = document.querySelector('#latest-imports');
  body.innerHTML = data.latest_imports.length ? data.latest_imports.map((item) => `<tr><td>#${item.id}</td><td>${statusTag(item.status)}</td><td>${item.total_rows}</td><td>${item.created_rows}</td><td>${item.updated_rows}</td><td>${dateTime(item.created_at)}</td></tr>`).join('') : '<tr><td colspan="6">尚无导入记录</td></tr>';
  refreshIcons();
}

async function loadStudents() {
  const keyword = document.querySelector('#student-search').value.trim();
  const filterForm = document.querySelector('#student-filters');
  const filterData = filterForm ? new FormData(filterForm) : new FormData();
  const params = new URLSearchParams({page: String(state.studentPage), page_size: String(state.studentPageSize)});
  if (keyword) params.set('keyword', keyword);
  ['school', 'college', 'school_major', 'current_class', 'gender', 'political_status', 'education_level', 'study_mode', 'sort_by', 'sort_direction'].forEach((field) => {
    const value = String(filterData.get(field) || '').trim();
    if (value) params.set(field, value);
  });
  const data = await api(`/api/students?${params.toString()}`);
  state.students = data.items;
  state.studentPage = data.page;
  state.studentPageSize = data.page_size;
  state.studentTotalPages = data.total_pages;
  const body = document.querySelector('#students-table');
  const empty = document.querySelector('#students-empty');
  empty.hidden = data.items.length > 0;
  body.innerHTML = data.items.map((student) => `<tr>
    <td class="select-column"><input type="checkbox" data-select-student="${student.id}"${state.selectedStudentIds.has(student.id) ? ' checked' : ''} aria-label="选择 ${escapeHTML(student.full_name)}"></td>
    <td>${escapeHTML(student.student_no)}<span class="subline">${escapeHTML(student.candidate_no || '-')}</span></td>
    <td><strong>${escapeHTML(student.full_name)}</strong><span class="subline">${escapeHTML(student.gender || '未填写')}</span></td>
    <td>${escapeHTML(student.school || '-')}<span class="subline">${escapeHTML(student.college || '-')}</span><span class="subline">${escapeHTML(student.school_major || '-')}</span></td>
    <td>${escapeHTML(student.current_class || '-')}<span class="subline">${escapeHTML(student.major_direction || '')}</span></td>
    <td>${escapeHTML(student.mobile_phone || '-')}<span class="subline">${escapeHTML(student.electronic_email || '')}</span></td>
    <td class="action-cell"><span class="student-inspection-actions" role="group" aria-label="学生档案查看"><button class="icon-button" data-source-id="${student.id}" title="查看数据来源" aria-label="查看${escapeHTML(student.full_name)}的数据来源"><i data-lucide="map-pin"></i></button><button class="icon-button" data-version-id="${student.id}" title="查看版本历史" aria-label="查看${escapeHTML(student.full_name)}的版本历史"><i data-lucide="history"></i></button><button class="icon-button" data-timeline-id="${student.id}" title="查看学生时间线" aria-label="查看${escapeHTML(student.full_name)}的学生时间线"><i data-lucide="list-tree"></i></button></span>${hasCapability('student_edit') ? `<span class="student-edit-actions" role="group" aria-label="学生档案编辑"><button class="icon-button" data-edit-id="${student.id}" title="编辑学生"><i data-lucide="pencil"></i></button><button class="icon-button danger-icon" data-delete-id="${student.id}" title="移入回收站"><i data-lucide="trash-2"></i></button></span>` : ''}</td>
  </tr>`).join('');
  body.querySelectorAll('[data-select-student]').forEach((checkbox) => checkbox.addEventListener('change', () => {
    const studentId = Number(checkbox.dataset.selectStudent);
    if (checkbox.checked) state.selectedStudentIds.add(studentId); else state.selectedStudentIds.delete(studentId);
    syncStudentSelectionControls();
  }));
  body.querySelectorAll('[data-edit-id]').forEach((button) => button.addEventListener('click', () => openStudentDialog(Number(button.dataset.editId))));
  body.querySelectorAll('[data-delete-id]').forEach((button) => button.addEventListener('click', () => deleteStudent(Number(button.dataset.deleteId))));
  body.querySelectorAll('[data-source-id]').forEach((button) => button.addEventListener('click', () => openSourceDialog(Number(button.dataset.sourceId))));
  body.querySelectorAll('[data-version-id]').forEach((button) => button.addEventListener('click', () => openVersionDialog(Number(button.dataset.versionId))));
  body.querySelectorAll('[data-timeline-id]').forEach((button) => button.addEventListener('click', () => openTimelineDialog(Number(button.dataset.timelineId))));
  document.querySelector('#student-page-summary').textContent = `共 ${data.total} 条，第 ${data.page} / ${data.total_pages} 页`;
  document.querySelector('#student-page-current').textContent = `${data.page} / ${data.total_pages}`;
  document.querySelector('#students-previous-page').disabled = data.page <= 1;
  document.querySelector('#students-next-page').disabled = data.page >= data.total_pages;
  syncStudentSelectionControls();
  refreshIcons();
}

function syncStudentSelectionControls() {
  const checkboxes = [...document.querySelectorAll('#students-table [data-select-student]')];
  const selectAll = document.querySelector('#students-select-all');
  const summary = document.querySelector('#student-selection-summary');
  const exportLabel = document.querySelector('#export-button-label');
  const selectedVisible = checkboxes.filter((checkbox) => checkbox.checked).length;
  if (selectAll) {
    selectAll.checked = checkboxes.length > 0 && selectedVisible === checkboxes.length;
    selectAll.indeterminate = selectedVisible > 0 && selectedVisible < checkboxes.length;
  }
  const selectedCount = state.selectedStudentIds.size;
  if (summary) summary.textContent = selectedCount ? `已选择 ${selectedCount} 名学生` : '未选择：导出全部';
  if (exportLabel) exportLabel.textContent = selectedCount ? `导出已选 ${selectedCount} 人` : '导出全部 XLSX';
  const bulkEdit = document.querySelector('#bulk-edit-students');
  if (bulkEdit) bulkEdit.hidden = !hasCapability('student_edit') || selectedCount === 0;
}

function clearStudentSelection() {
  state.selectedStudentIds.clear();
  syncStudentSelectionControls();
}

function openBulkStudentDialog() {
  const count = state.selectedStudentIds.size;
  if (!count) { toast('请先在学生列表中选择至少一名学生。', true); return; }
  const dialog = document.querySelector('#bulk-student-dialog');
  const form = document.querySelector('#bulk-student-form');
  form.reset();
  form.querySelectorAll('[data-bulk-enable]').forEach((checkbox) => {
    form.elements[checkbox.dataset.bulkEnable].disabled = true;
  });
  document.querySelector('#bulk-student-summary').textContent = `将对已选择的 ${count} 名学生统一更新。仅勾选的字段会被写入；勾选后留空可清空该字段。每名学生都会保留独立版本和审计记录。`;
  document.querySelector('#bulk-student-error').textContent = '';
  dialog.showModal();
}

async function saveBulkStudents(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#bulk-student-error');
  error.textContent = '';
  const changes = {};
  form.querySelectorAll('[data-bulk-enable]').forEach((checkbox) => {
    if (checkbox.checked) changes[checkbox.dataset.bulkEnable] = form.elements[checkbox.dataset.bulkEnable].value;
  });
  const fields = Object.keys(changes);
  if (!fields.length) { error.textContent = '请至少勾选一个要更新的字段。'; return; }
  const count = state.selectedStudentIds.size;
  if (!confirm(`确认批量更新 ${count} 名学生的“${fields.map(fieldLabel).join('、')}”？`)) return;
  try {
    const result = await api('/api/students/bulk-update', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({student_ids:[...state.selectedStudentIds], changes})});
    document.querySelector('#bulk-student-dialog').close();
    clearStudentSelection();
    toast(`已更新 ${result.updated} 名学生${result.unchanged ? `，${result.unchanged} 名无需变更` : ''}`);
    await Promise.all([loadStudents(), loadDashboard()]);
  } catch (errorObject) { error.textContent = errorObject.message; }
}

function setFilterSelectOptions(select, values, emptyLabel) {
  if (!select) return;
  const selected = select.value;
  select.innerHTML = `<option value="">${escapeHTML(emptyLabel)}</option>${values.map((value) => `<option value="${escapeHTML(value)}">${escapeHTML(value)}</option>`).join('')}`;
  select.value = values.includes(selected) ? selected : '';
}

async function loadStudentFilterOptions() {
  const form = document.querySelector('#student-filters');
  if (!form) return;
  const school = form.elements.school.value;
  const college = form.elements.college.value;
  const schoolMajor = form.elements.school_major.value;
  const params = new URLSearchParams();
  if (school) params.set('school', school);
  if (college) params.set('college', college);
  if (schoolMajor) params.set('school_major', schoolMajor);
  const data = await api(`/api/students/filter-options?${params.toString()}`);
  setFilterSelectOptions(form.elements.school, data.schools || [], '全部学校');
  setFilterSelectOptions(form.elements.college, data.colleges || [], '全部学院');
  setFilterSelectOptions(form.elements.school_major, data.majors || [], '全部专业');
  setFilterSelectOptions(form.elements.current_class, data.classes || [], '全部班级');
  setFilterSelectOptions(form.elements.political_status, data.political_statuses || [], '全部政治面貌');
}

const savedStudentFilterFields = ['school', 'college', 'school_major', 'current_class', 'gender', 'political_status', 'sort_by', 'sort_direction'];

function collectStudentFilter() {
  const form = document.querySelector('#student-filters');
  const filters = Object.fromEntries(savedStudentFilterFields.map((field) => [field, String(form.elements[field]?.value || '').trim()]).filter(([, value]) => value));
  const keyword = document.querySelector('#student-search')?.value.trim();
  if (keyword) filters.keyword = keyword;
  return filters;
}

async function loadSavedStudentFilters() {
  const data = await api('/api/student-filters');
  state.savedStudentFilters = data;
  const select = document.querySelector('#saved-student-filter');
  if (!select) return;
  const selected = select.value;
  select.innerHTML = `<option value="">选择已保存筛选</option>${data.map((item) => `<option value="${item.id}">${escapeHTML(item.name)}</option>`).join('')}`;
  select.value = data.some((item) => String(item.id) === selected) ? selected : '';
}

async function applySavedStudentFilter() {
  const id = Number(document.querySelector('#saved-student-filter').value);
  const saved = state.savedStudentFilters.find((item) => item.id === id);
  if (!saved) return;
  const filters = saved.filters || {};
  const form = document.querySelector('#student-filters');
  document.querySelector('#student-search').value = filters.keyword || '';
  const params = new URLSearchParams();
  ['school', 'college', 'school_major'].forEach((field) => { if (filters[field]) params.set(field, filters[field]); });
  const options = await api(`/api/students/filter-options?${params.toString()}`);
  setFilterSelectOptions(form.elements.school, options.schools || [], '全部学校');
  setFilterSelectOptions(form.elements.college, options.colleges || [], '全部学院');
  setFilterSelectOptions(form.elements.school_major, options.majors || [], '全部专业');
  setFilterSelectOptions(form.elements.current_class, options.classes || [], '全部班级');
  setFilterSelectOptions(form.elements.political_status, options.political_statuses || [], '全部政治面貌');
  savedStudentFilterFields.forEach((field) => { if (form.elements[field] && field !== 'school' && field !== 'college' && field !== 'school_major' && field !== 'current_class' && field !== 'political_status') form.elements[field].value = filters[field] || form.elements[field].value; });
  ['school', 'college', 'school_major', 'current_class', 'gender', 'political_status', 'sort_by', 'sort_direction'].forEach((field) => { if (form.elements[field] && filters[field]) form.elements[field].value = filters[field]; });
  clearStudentSelection();
  state.studentPage = 1;
  await loadStudents();
}

async function saveCurrentStudentFilter() {
  const name = window.prompt('请输入常用筛选名称：');
  if (!name?.trim()) return;
  try {
    const saved = await api('/api/student-filters', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name.trim(), filters:collectStudentFilter()})});
    toast('常用筛选已保存');
    await loadSavedStudentFilters();
    document.querySelector('#saved-student-filter').value = String(saved.id);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function deleteSavedStudentFilter() {
  const id = Number(document.querySelector('#saved-student-filter').value);
  const saved = state.savedStudentFilters.find((item) => item.id === id);
  if (!saved || !confirm(`删除常用筛选“${saved.name}”？`)) return;
  try { await api(`/api/student-filters/${id}`, {method:'DELETE'}); toast('常用筛选已删除'); await loadSavedStudentFilters(); } catch (errorObject) { toast(errorObject.message, true); }
}

function resetStudentFilterDescendants(fieldName) {
  const form = document.querySelector('#student-filters');
  if (!form) return;
  if (fieldName === 'school') {
    form.elements.college.value = '';
    form.elements.school_major.value = '';
    form.elements.current_class.value = '';
  } else if (fieldName === 'college') {
    form.elements.school_major.value = '';
    form.elements.current_class.value = '';
  } else if (fieldName === 'school_major') {
    form.elements.current_class.value = '';
  }
}

async function handleStudentFilterChange(event) {
  clearStudentSelection();
  state.studentPage = 1;
  resetStudentFilterDescendants(event.target.name);
  try {
    await loadStudentFilterOptions();
    await loadStudents();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadImports() {
  const [data] = await Promise.all([api('/api/imports'), loadImportTemplateOptions()]);
  state.importReportCache = {};
  const modeLabels = {upsert:'学生数据新增或更新', create_only:'学生数据仅新增', update_only:'学生数据仅更新', related_info:'学生相关信息备注导入'};
  const body = document.querySelector('#imports-table');
  body.innerHTML = data.length ? data.map((item) => {
    const filename = item.document_available ? `<a href="/api/documents/${item.document_id}/download">${escapeHTML(item.filename)}</a>` : `<span>${escapeHTML(item.filename)}</span>`;
    const reportControl = `<button class="text-button import-report-trigger" type="button" data-import-report="${item.id}" title="悬停查看导入报告" aria-haspopup="dialog">报告</button>`;
    const undoControl = item.can_undo_latest ? `<button class="text-button danger-text" data-rollback-import="${item.id}" data-import-name="${escapeHTML(item.filename)}">撤销本人最近导入</button>` : '';
    return `<tr><td>${filename}</td><td>${escapeHTML(modeLabels[item.mode] || item.mode)}</td><td>${statusTag(item.status)}${item.rollback_status ? `<span class="subline">撤销：${escapeHTML(item.rollback_status)}</span>` : ''}</td><td>${item.total_rows}</td><td>${item.created_rows} / ${item.updated_rows} / ${item.skipped_rows}</td><td>${dateTime(item.created_at)}</td><td class="action-cell"><span class="import-action-links">${reportControl}${undoControl}</span></td></tr>`;
  }).join('') : '<tr><td colspan="7">尚无导入记录</td></tr>';
  body.querySelectorAll('[data-rollback-import]').forEach((button) => button.addEventListener('click', () => rollbackImportBatch(Number(button.dataset.rollbackImport), button.dataset.importName)));
  body.querySelectorAll('[data-import-report]').forEach((button) => {
    button.addEventListener('pointerenter', () => showImportReportPreview(button));
    button.addEventListener('pointerleave', scheduleImportReportHide);
    button.addEventListener('focus', () => showImportReportPreview(button));
    button.addEventListener('blur', hideImportReportPreview);
  });
}

function importReportMarkup(report) {
  const modeLabels = {upsert:'学生数据新增或更新', create_only:'学生数据仅新增', update_only:'学生数据仅更新', related_info:'学生相关信息备注导入'};
  const errors = report.errors?.length
    ? `<div class="import-report-scroll">${report.errors.map((item) => `<div class="import-report-error"><b>${escapeHTML(item.row)} 行</b><span>${escapeHTML(item.message)}</span></div>`).join('')}${report.errors_truncated ? '<p class="subline">仅显示前 80 条错误。</p>' : ''}</div>`
    : '<p class="import-report-empty">未记录错误明细。</p>';
  const createdChanges = report.rollback_changes?.created || [];
  const updatedChanges = report.rollback_changes?.updated || [];
  const changes = [...createdChanges.map((item) => ({...item, type:'新增'})), ...updatedChanges.map((item) => ({...item, type:'更新'}))];
  const rollback = changes.length
    ? `<div class="import-report-scroll compact">${changes.map((item) => `<div class="import-report-change"><b>${escapeHTML(item.type)} · ${escapeHTML(item.student_no)}</b><span>${escapeHTML(item.fields)}</span></div>`).join('')}</div>`
    : '<p class="import-report-empty">没有可展示的撤销变更。</p>';
  const errorActions = report.error_rows ? `<div class="import-report-actions"><a class="text-button" href="/api/imports/${report.id}/errors.csv">下载错误明细</a>${report.mode === 'related_info' ? '<button class="text-button" type="button" data-open-import-match-review>前往人工匹配</button>' : `<a class="text-button" href="/api/imports/${report.id}/errors.xlsx">下载错误行修正模板</a><button class="text-button" type="button" data-open-import-retry="${report.id}">上传修正后重试</button>`}</div>` : '';
  return `<div class="import-report-head"><div><p class="eyebrow">IMPORT REPORT</p><h3>${escapeHTML(report.filename)}</h3></div><button class="icon-button" type="button" data-close-import-report title="关闭报告"><i data-lucide="x"></i></button></div><div class="import-report-body"><dl class="import-report-meta"><div><dt>导入方式</dt><dd>${escapeHTML(modeLabels[report.mode] || report.mode)}</dd></div><div><dt>导入状态</dt><dd>${statusTag(report.status)}</dd></div><div><dt>导入人</dt><dd>${escapeHTML(report.imported_by)}</dd></div><div><dt>完成时间</dt><dd>${dateTime(report.completed_at || report.created_at)}</dd></div></dl><div class="import-report-metrics"><div><span>总行数</span><b>${report.total_rows}</b></div><div><span>新增</span><b>${report.created_rows}</b></div><div><span>更新</span><b>${report.updated_rows}</b></div><div><span>跳过</span><b>${report.skipped_rows}</b></div><div class="error"><span>错误</span><b>${report.error_rows}</b></div></div><section class="import-report-section"><div><h4>错误明细</h4><span>${report.error_rows} 条</span></div>${errors}${errorActions}</section><section class="import-report-section"><div><h4>可撤销变更</h4><span>${escapeHTML(report.rollback_status)} · 新增 ${report.rollback_created} / 更新 ${report.rollback_updated}</span></div>${rollback}</section></div>`;
}

function placeImportReportPopover(trigger) {
  const popover = document.querySelector('#import-report-popover');
  const rect = trigger.getBoundingClientRect();
  const gap = 8;
  const width = popover.offsetWidth;
  const height = popover.offsetHeight;
  let left = rect.right + gap;
  if (left + width > window.innerWidth - 12) left = Math.max(12, rect.left - width - gap);
  let top = rect.top;
  if (top + height > window.innerHeight - 12) top = Math.max(12, window.innerHeight - height - 12);
  popover.style.left = `${Math.round(left)}px`;
  popover.style.top = `${Math.round(top)}px`;
}

function hideImportReportPreview() {
  clearTimeout(state.importReportHideTimer);
  state.importReportHideTimer = null;
  state.importReportTrigger = null;
  document.querySelector('#import-report-popover').hidden = true;
}

function scheduleImportReportHide() {
  clearTimeout(state.importReportHideTimer);
  state.importReportHideTimer = window.setTimeout(hideImportReportPreview, 160);
}

function handleImportReportScroll(event) {
  const target = event.target;
  if (target && typeof target.closest === 'function' && target.closest('#import-report-popover')) return;
  hideImportReportPreview();
}

async function showImportReportPreview(trigger) {
  const batchId = Number(trigger.dataset.importReport);
  if (!batchId) return;
  clearTimeout(state.importReportHideTimer);
  state.importReportTrigger = trigger;
  const popover = document.querySelector('#import-report-popover');
  popover.hidden = false;
  popover.innerHTML = '<div class="import-report-loading">正在读取导入报告...</div>';
  placeImportReportPopover(trigger);
  try {
    const report = state.importReportCache[batchId] || await api(`/api/imports/${batchId}/report`);
    state.importReportCache[batchId] = report;
    if (state.importReportTrigger !== trigger) return;
    popover.innerHTML = importReportMarkup(report);
    refreshIcons();
    placeImportReportPopover(trigger);
  } catch (errorObject) {
    if (state.importReportTrigger !== trigger) return;
    popover.innerHTML = `<div class="import-report-loading error">${escapeHTML(errorObject.message)}</div>`;
    placeImportReportPopover(trigger);
  }
}

async function rollbackImportBatch(batchId, filename) {
  if (!confirm(`撤销本人最近一次导入“${filename}”会移除该批次尚未审核的信息、已写入的 Excel 词条，并在未发生后续修改时恢复相关备注或学生字段。继续二次确认？`)) return;
  if (window.prompt('二次确认：请输入“撤销导入”继续：') !== '撤销导入') return;
  try {
    const result = await api(`/api/imports/${batchId}/rollback`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_phrase:'撤销导入'})});
    toast(result.message || '导入批次已撤销');
    await Promise.all([loadImports(), loadStudents(), loadDashboard()]);
  } catch (errorObject) { toast(errorObject.message, true); }
}

function openImportRetryDialog(batchId) {
  const dialog = document.querySelector('#import-retry-dialog');
  const form = document.querySelector('#import-retry-form');
  form.reset();
  form.dataset.batchId = String(batchId);
  document.querySelector('#import-retry-error').textContent = '';
  document.querySelector('#import-retry-file-name').textContent = '请先下载错误行修正模板，修正后上传';
  dialog.showModal();
}

async function retryImportErrors(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const file = form.elements.file.files[0];
  const error = document.querySelector('#import-retry-error');
  error.textContent = '';
  if (!file) { error.textContent = '请选择修正后的 Excel 文件。'; return; }
  const data = new FormData();
  data.append('file', file);
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await api(`/api/imports/${form.dataset.batchId}/retry-errors`, {method:'POST', body:data});
    document.querySelector('#import-retry-dialog').close();
    toast(result.error_rows ? `已创建重试批次，仍有 ${result.error_rows} 条错误` : '错误行已修正并重新导入');
    await Promise.all([loadImports(), loadStudents(), loadDashboard()]);
  } catch (errorObject) { error.textContent = errorObject.message; }
  finally { button.disabled = false; }
}

async function loadImportTemplateOptions() {
  if (!['super_admin', 'admin'].includes(state.user?.role)) return;
  const templates = await api('/api/import-templates');
  state.importTemplates = templates;
  const select = document.querySelector('#import-template-select');
  if (!select) return;
  const selected = select.value;
  select.innerHTML = `<option value="">不使用模板</option>${templates.map((template) => `<option value="${template.id}">${escapeHTML(template.name)}</option>`).join('')}`;
  select.value = templates.some((template) => String(template.id) === selected) ? selected : '';
}

async function loadSystemSettings() {
  if (!['super_admin', 'admin'].includes(state.user?.role)) return;
  const data = await api('/api/system/settings');
  const isSuperAdmin = state.user.role === 'super_admin';
  const settingsSections = [...document.querySelectorAll('#view-settings > .tool-surface, #view-settings > .section-block')];
  const superOnlySections = new Set([2, 3, 4, 5, 6, 8]);
  settingsSections.forEach((section, index) => { section.hidden = !isSuperAdmin && superOnlySections.has(index); });
  document.querySelector('#view-settings > .tool-surface h2').textContent = isSuperAdmin ? '超级管理员' : '管理员设置';
  const accountSection = settingsSections[1];
  accountSection.querySelector('.section-heading p').textContent = isSuperAdmin ? '超级管理员可创建管理员和教师，并分别配置数据范围与可执行功能。' : '普通管理员只能创建、编辑、重置教师账号，并管理教师的数据范围。';
  document.querySelector('#new-administrator-button').lastChild.textContent = isSuperAdmin ? '新增账号' : '新增教师账号';
  const form = document.querySelector('#system-settings-form');
  form.elements.username.value = data.username;
  form.elements.display_name.value = data.display_name;
  form.elements.current_password.value = '';
  form.elements.new_password.value = '';
  form.elements.confirm_password.value = '';
  document.querySelector('#system-settings-error').textContent = '';
  const tasks = [loadAdministrators(), loadDataScopes(), loadSystemUpdate()];
  if (isSuperAdmin) tasks.push(loadBackups(), loadSystemInfo(), loadSystemControls(), loadImportTemplates(), loadExportTemplates());
  await Promise.all(tasks);
}

const ACTIVE_SYSTEM_UPDATE_STATES = new Set(['queued', 'downloading', 'validating', 'backing_up', 'applying', 'installing', 'restarting', 'rolling_back']);

function systemUpdateStateLabel(stateValue) {
  const labels = {
    idle: '未执行更新', queued: '已排队', downloading: '正在下载', validating: '正在校验', backing_up: '正在备份',
    applying: '正在替换程序', installing: '正在安装依赖', restarting: '正在重启服务', rolling_back: '正在回滚',
    completed: '更新完成', failed: '更新失败', unknown: '状态未知',
  };
  return labels[stateValue] || stateValue || '未执行更新';
}

function renderSystemUpdate(data) {
  const summary = document.querySelector('#system-update-summary');
  const releaseNode = document.querySelector('#system-update-release');
  const executeForm = document.querySelector('#system-update-execute-form');
  const configForm = document.querySelector('#system-update-config-form');
  if (!summary || !releaseNode || !executeForm || !configForm) return;
  const configuration = data.configuration || {};
  const updateStatus = data.status || {state: 'idle'};
  const release = state.latestSystemUpdate?.release || null;
  const statusState = String(updateStatus.state || 'idle');
  const progress = Math.max(0, Math.min(100, Number(updateStatus.progress || 0)));
  summary.innerHTML = `<div class="system-update-current"><span>当前版本</span><strong>${escapeHTML(data.current_version || configuration.current_version || '-')}</strong></div><div class="system-update-current"><span>更新来源</span><strong>${escapeHTML(configuration.repository || '未配置')}</strong><small>${escapeHTML(configuration.channel === 'beta' ? '测试通道' : '稳定通道')}${configuration.has_token ? ' · 已配置访问令牌' : ''}</small></div><div class="system-update-current update-status-${escapeHTML(statusState)}"><span>${escapeHTML(systemUpdateStateLabel(statusState))}</span><strong>${progress}%</strong><small>${escapeHTML(updateStatus.message || '等待管理员操作')}</small></div>`;
  if (!state.latestSystemUpdate) {
    releaseNode.innerHTML = '<p class="source-empty">点击“检查更新”后，系统将从受控 GitHub Release 获取可安装版本。</p>';
  } else if (!release) {
    releaseNode.innerHTML = `<p class="source-empty">${escapeHTML(state.latestSystemUpdate.message || '暂未找到可用更新版本。')}</p>`;
  } else {
    const ready = Boolean(release.update_ready);
    const newer = Boolean(release.is_newer);
    const availability = ready && newer ? '发现可安装的新版本' : ready ? '当前已是最新版本' : '该 Release 缺少受控更新包';
    releaseNode.innerHTML = `<div class="system-update-release-card"><div><span class="eyebrow">GITHUB RELEASE</span><h3>${escapeHTML(release.name || release.tag_name || '未命名版本')}</h3><p>${escapeHTML(availability)}</p>${release.body ? `<p class="system-update-notes">${escapeHTML(release.body)}</p>` : ''}</div><div class="system-update-release-meta"><strong>${escapeHTML(release.tag_name || '-')}</strong><span>${escapeHTML(dateTime(release.published_at))}</span><span>${release.package?.size ? `${Math.ceil(Number(release.package.size) / 1024 / 1024)} MB` : ''}</span></div></div>`;
  }
  const canExecute = Boolean(data.may_execute && release?.update_ready && release?.is_newer && !ACTIVE_SYSTEM_UPDATE_STATES.has(statusState));
  executeForm.hidden = !canExecute;
  executeForm.elements.tag_name.value = release?.tag_name || '';
  configForm.hidden = !data.may_configure;
  if (data.may_configure && !configForm.contains(document.activeElement)) {
    configForm.elements.repository.value = configuration.repository || 'Star-Moon10/Student-Management-System';
    configForm.elements.channel.value = configuration.channel || 'stable';
    configForm.elements.github_token.value = '';
    configForm.elements.current_password.value = '';
  }
  clearTimeout(state.systemUpdateTimer);
  if (ACTIVE_SYSTEM_UPDATE_STATES.has(statusState)) {
    state.systemUpdateTimer = window.setTimeout(() => loadSystemUpdate().catch((errorObject) => toast(errorObject.message, true)), 2000);
  }
  refreshIcons();
}

async function loadSystemUpdate(check = false) {
  const data = await api('/api/system/updates');
  if (check) state.latestSystemUpdate = await api('/api/system/updates/check', {method:'POST'});
  renderSystemUpdate(data);
  return data;
}

async function saveSystemUpdateConfiguration(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#system-update-config-error');
  error.textContent = '';
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await api('/api/system/updates/config', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.fromEntries(new FormData(form).entries()))});
    state.latestSystemUpdate = null;
    form.elements.github_token.value = '';
    form.elements.current_password.value = '';
    await loadSystemUpdate();
    toast('更新来源已保存。');
  } catch (errorObject) {
    error.textContent = errorObject.message;
  } finally {
    button.disabled = false;
  }
}

async function startSystemUpdate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#system-update-execute-error');
  error.textContent = '';
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await api('/api/system/updates/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.fromEntries(new FormData(form).entries()))});
    form.reset();
    toast(result.message || '更新器已启动。');
    await loadSystemUpdate();
  } catch (errorObject) {
    error.textContent = errorObject.message;
  } finally {
    button.disabled = false;
  }
}

async function startOfflineSystemUpdate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#system-update-offline-error');
  error.textContent = '';
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const result = await api('/api/system/updates/offline', {method:'POST', body:new FormData(form)});
    form.reset();
    form.closest('details').open = false;
    toast(result.message || '离线更新器已启动。');
    await loadSystemUpdate();
  } catch (errorObject) {
    error.textContent = errorObject.message;
  } finally {
    button.disabled = false;
  }
}

async function saveSystemSettings(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#system-settings-error');
  error.textContent = '';
  const payload = Object.fromEntries(new FormData(form).entries());
  if (!payload.new_password) {
    payload.new_password = null;
    payload.confirm_password = null;
  }
  try {
    await api('/api/system/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    await loadUser();
    await loadSystemSettings();
    toast('系统设置已保存');
  } catch (errorObject) {
    error.textContent = errorObject.message;
  }
}

function openHighRiskSettings() {
  if (state.user?.role !== 'super_admin') return;
  const dialog = document.querySelector('#high-risk-dialog');
  const form = document.querySelector('#high-risk-auth-form');
  state.highRiskApproval = null;
  form.reset();
  document.querySelector('#high-risk-auth-panel').hidden = false;
  document.querySelector('#high-risk-actions').hidden = true;
  document.querySelector('#high-risk-error').textContent = '';
  document.querySelector('#high-risk-approval-state').textContent = '';
  dialog.showModal();
}

async function authorizeHighRiskSettings(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#high-risk-error');
  error.textContent = '';
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    const result = await api('/api/system/high-risk/authorize', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...payload, action:'clear_all_students'})});
    state.highRiskApproval = result;
    form.elements.password.value = '';
    document.querySelector('#high-risk-auth-panel').hidden = true;
    document.querySelector('#high-risk-actions').hidden = false;
    document.querySelector('#high-risk-approval-state').textContent = `授权成功，有效期至 ${dateTime(result.expires_at)}。执行后授权立即失效。`;
    refreshIcons();
  } catch (errorObject) {
    error.textContent = errorObject.message;
  }
}

async function clearAllStudentsHighRisk() {
  if (!state.highRiskApproval?.approval_id) {
    toast('请先验证超级管理员凭证。', true);
    return;
  }
  if (!window.confirm('第一次确认：确定要清空当前全部学生档案吗？学生档案将移入回收站。')) return;
  if (!window.confirm('第二次确认：该操作会处理全部活动学生及其相关词条，确定继续吗？')) return;
  const phrase = window.prompt('第三次确认：请输入“永久清空学生档案”后继续。');
  if (phrase !== '永久清空学生档案') {
    if (phrase !== null) toast('确认口令不正确，操作已取消。', true);
    return;
  }
  const button = document.querySelector('#high-risk-clear-students');
  button.disabled = true;
  try {
    const result = await api('/api/system/high-risk/clear-students', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({approval_id:state.highRiskApproval.approval_id, confirmation_count:3, confirmation_phrase:phrase})});
    state.highRiskApproval = null;
    document.querySelector('#high-risk-dialog').close();
    toast(`高危操作已完成，${result.deleted_students || 0} 名学生已移入回收站。`);
    await Promise.all([loadDashboard(), loadStudents(), loadCandidates(), loadRecycleBin()]);
  } catch (errorObject) {
    toast(errorObject.message, true);
  } finally {
    button.disabled = false;
  }
}

async function loadAdministrators() {
  if (!['super_admin', 'admin'].includes(state.user?.role)) return;
  const administrators = await api('/api/system/administrators');
  state.administrators = administrators;
  const body = document.querySelector('#administrators-table');
  const roleLabels = {admin:'管理员', teacher:'教师'};
  body.innerHTML = administrators.length ? administrators.map((administrator) => `<tr>
    <td><strong>${escapeHTML(administrator.display_name)}</strong><span class="subline">${escapeHTML(roleLabels[administrator.role] || administrator.role)}</span></td>
    <td>${escapeHTML(administrator.username)}</td>
    <td>${escapeHTML(roleLabels[administrator.role] || administrator.role)}</td>
    <td>${escapeHTML((administrator.capabilities || []).map(capabilityLabel).join('、') || '无')}</td>
    <td>${dateTime(administrator.created_at)}</td>
    <td>${dateTime(administrator.last_login_at)}</td>
    <td class="action-cell"><button class="icon-button" data-edit-administrator-id="${administrator.id}" title="编辑账号或重置密码"><i data-lucide="pencil"></i></button><button class="icon-button danger-icon" data-revoke-sessions-id="${administrator.id}" title="强制注销全部会话"><i data-lucide="log-out"></i></button></td>
  </tr>`).join('') : '<tr><td colspan="7">尚无账号</td></tr>';
  body.querySelectorAll('[data-edit-administrator-id]').forEach((button) => button.addEventListener('click', () => openAdministratorDialog(Number(button.dataset.editAdministratorId))));
  body.querySelectorAll('[data-revoke-sessions-id]').forEach((button) => button.addEventListener('click', () => revokeAdministratorSessions(Number(button.dataset.revokeSessionsId))));
  refreshIcons();
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function loadBackups() {
  if (state.user?.role !== 'super_admin') return;
  const backups = await api('/api/system/backups');
  const body = document.querySelector('#backups-table');
  body.innerHTML = backups.length ? backups.map((backup) => `<tr><td>${backup.status === 'completed' ? `<a href="/api/system/backups/${backup.id}/download">${escapeHTML(backup.file_name || '-')}</a>` : escapeHTML(backup.file_name || '-')}<span class="subline">原始文件 ${backup.storage_files || 0} 个${backup.offsite_status ? ` · 异地 ${escapeHTML(backup.offsite_status)}` : ''}</span></td><td>${escapeHTML(backup.database_dialect)}</td><td>${formatBytes(backup.size_bytes)}</td><td>${statusTag(backup.status)}${backup.validation_status ? `<span class="subline">校验 ${escapeHTML(backup.validation_status)}</span>` : ''}</td><td>${dateTime(backup.created_at)}${backup.error_message ? `<span class="subline">${escapeHTML(backup.error_message)}</span>` : ''}<span class="table-actions">${backup.status === 'completed' ? `<button class="text-button" data-validate-backup="${backup.id}">校验</button><button class="text-button" data-drill-backup="${backup.id}">演练</button><button class="text-button danger-text" data-restore-backup="${backup.id}">恢复</button>` : ''}<button class="text-button danger-text" data-delete-backup="${backup.id}" data-backup-name="${escapeHTML(backup.file_name || '该备份')}">删除</button></span></td></tr>`).join('') : '<tr><td colspan="5">尚无备份记录</td></tr>';
  body.querySelectorAll('[data-validate-backup]').forEach((button) => button.addEventListener('click', () => validateBackup(Number(button.dataset.validateBackup))));
  body.querySelectorAll('[data-drill-backup]').forEach((button) => button.addEventListener('click', () => drillBackup(Number(button.dataset.drillBackup))));
  body.querySelectorAll('[data-restore-backup]').forEach((button) => button.addEventListener('click', () => restoreBackup(Number(button.dataset.restoreBackup))));
  body.querySelectorAll('[data-delete-backup]').forEach((button) => button.addEventListener('click', () => deleteBackup(Number(button.dataset.deleteBackup), button.dataset.backupName)));
}

async function createBackup() {
  if (!confirm('确认立即创建数据库备份？')) return;
  const button = document.querySelector('#create-backup-button');
  button.disabled = true;
  try {
    await api('/api/system/backups', {method:'POST'});
    toast('数据库备份已完成');
    await loadBackups();
  } catch (errorObject) {
    toast(errorObject.message, true);
  } finally {
    button.disabled = false;
  }
}

async function validateBackup(id) {
  try {
    await api(`/api/system/backups/${id}/validate`, {method:'POST'});
    toast('备份包与原始文件校验通过');
    await loadBackups();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function drillBackup(id) {
  if (!confirm('将在临时隔离目录中解压并校验该备份，不会修改当前数据库。确认开始演练？')) return;
  try {
    const result = await api(`/api/system/backups/${id}/drill`, {method:'POST'});
    const detail = result.result || {};
    const metrics = `${detail.student_count == null ? '学生数待 MySQL 维护窗口校验' : `学生 ${detail.student_count} 名`} · 数据表 ${detail.table_count ?? '-'} 张`;
    toast(`${result.message || '隔离恢复演练通过'}（${metrics}）`);
    await loadBackups();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function restoreBackup(id) {
  const phrase = window.prompt('恢复只会替换学生档案及其相关资料，并先创建一个回滚备份。账号、审计、AI 记录、系统设置和所有备份记录会保留。请输入“恢复备份”继续：');
  if (phrase !== '恢复备份') return;
  try {
    const result = await api(`/api/system/backups/${id}/restore`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_phrase: phrase})});
    toast(result.message || '备份已恢复');
    await refreshAll();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function deleteBackup(id, fileName) {
  if (!window.confirm(`将永久删除“${fileName}”的本地备份文件、异地副本（如有）和备份记录，无法恢复。继续进入二次确认？`)) return;
  const phrase = window.prompt('二次确认：请输入“删除备份”以永久删除该备份：');
  if (phrase !== '删除备份') return;
  try {
    const result = await api(`/api/system/backups/${id}`, {method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_phrase: phrase})});
    toast(result.message || '备份已删除');
    await loadBackups();
  } catch (errorObject) { toast(errorObject.message, true); }
}

function systemInfoCard(label, value, detail = '') {
  return `<article class="system-info-card"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong>${detail ? `<small>${escapeHTML(detail)}</small>` : ''}</article>`;
}

async function loadSystemInfo() {
  if (state.user?.role !== 'super_admin') return;
  const target = document.querySelector('#system-info-grid');
  if (!target) return;
  try {
    const info = await api('/api/system/info');
    const storage = info.storage || {};
    const security = info.security || {};
    target.innerHTML = [
      systemInfoCard('系统版本', `v${info.release || '-'}`, `环境：${security.environment || '-'}`),
      systemInfoCard('数据库', `${info.database?.dialect || '-'} · ${info.database?.students ?? 0} 名学生`, `${info.database?.tables ?? 0} 张数据表`),
      systemInfoCard('导出文件', `${storage.exports?.files ?? 0} 个 · ${formatBytes(storage.exports?.size_bytes)}`, '仅生成文件可自动清理'),
      systemInfoCard('原始资料', `${storage.originals?.files ?? 0} 个 · ${formatBytes(storage.originals?.size_bytes)}`, '不会被维护操作删除'),
      systemInfoCard('备份文件', `${storage.backups?.files ?? 0} 个 · ${formatBytes(storage.backups?.size_bytes)}`, '由备份策略单独管理'),
      systemInfoCard('可用磁盘', `${formatBytes(storage.disk_free_bytes)} / ${formatBytes(storage.disk_total_bytes)}`, `无操作自动登出：${security.idle_logout_minutes || 5} 分钟`),
    ].join('');
  } catch (errorObject) {
    target.innerHTML = `<p class="source-empty">${escapeHTML(errorObject.message)}</p>`;
  }
}

async function cleanupOldExports() {
  const value = window.prompt('仅会删除已生成的 XLSX/CSV 导出文件，不会删除学生档案、原始资料或备份。请输入保留天数：', '30');
  if (value === null) return;
  const retentionDays = Number(value);
  if (!Number.isInteger(retentionDays) || retentionDays < 1) { toast('请输入至少 1 天的整数。', true); return; }
  if (!confirm(`确认删除 ${retentionDays} 天前生成的导出文件？此操作无法撤回。`)) return;
  try {
    const result = await api('/api/system/maintenance/cleanup-exports', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({retention_days:retentionDays})});
    toast(`已清理 ${result.deleted_files} 个导出文件，释放 ${formatBytes(result.freed_bytes)}`);
    await loadSystemInfo();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadSystemControls() {
  if (state.user?.role !== 'super_admin') return;
  const controls = await api('/api/system/controls');
  const form = document.querySelector('#system-controls-form');
  Object.entries(controls).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].checked = Boolean(value); });
}

async function saveSystemControls(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = Object.fromEntries(['ai_operations_enabled', 'ai_export_confirmation_required'].map((key) => [key, Boolean(form.elements[key]?.checked)]));
  try {
    await api('/api/system/controls', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    toast('AI 控制已保存');
  } catch (errorObject) { toast(errorObject.message, true); }
}

function normalizeTemplateField(value) {
  const text = String(value || '').trim();
  if (importableStudentFields.includes(text)) return text;
  return importableStudentFields.find((field) => fieldLabel(field) === text) || null;
}

async function loadImportTemplates() {
  if (state.user?.role !== 'super_admin') return;
  const templates = await api('/api/import-templates');
  const body = document.querySelector('#import-templates-table');
  body.innerHTML = templates.length ? templates.map((template) => `<tr><td><strong>${escapeHTML(template.name)}</strong><span class="subline">${Object.keys(template.mapping || {}).length} 个映射列</span></td><td>${escapeHTML(template.default_mode)}</td><td>${template.update_policy === 'only_blank' ? '仅补空值' : '覆盖已有值'}</td><td>${escapeHTML((template.required_fields || []).map(fieldLabel).join('、') || '-')}</td><td>${dateTime(template.updated_at)}</td><td class="action-cell"><button class="icon-button" title="查看模板版本" data-template-history-kind="import" data-template-history-id="${template.id}" data-template-history-name="${escapeHTML(template.name)}"><i data-lucide="history"></i></button><button class="icon-button danger-icon" title="删除模板" data-delete-template="${template.id}"><i data-lucide="trash-2"></i></button></td></tr>`).join('') : '<tr><td colspan="6">尚无导入模板</td></tr>';
  body.querySelectorAll('[data-delete-template]').forEach((button) => button.addEventListener('click', () => deleteImportTemplate(Number(button.dataset.deleteTemplate))));
  body.querySelectorAll('[data-template-history-kind]').forEach((button) => button.addEventListener('click', () => openTemplateHistory(button.dataset.templateHistoryKind, Number(button.dataset.templateHistoryId), button.dataset.templateHistoryName)));
  refreshIcons();
  await loadImportTemplateOptions();
}

async function saveImportTemplate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  let mapping = {};
  try { mapping = form.elements.mapping_json.value.trim() ? JSON.parse(form.elements.mapping_json.value.trim()) : {}; } catch (_) { toast('字段映射必须是合法 JSON。', true); return; }
  const requiredFields = form.elements.required_fields.value.split(/[,，]/).map(normalizeTemplateField).filter(Boolean);
  try {
    await api('/api/import-templates', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:form.elements.name.value, default_mode:form.elements.default_mode.value, update_policy:form.elements.update_policy.value, required_fields:requiredFields, mapping})});
    form.reset();
    toast('导入模板已保存');
    await loadImportTemplates();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function deleteImportTemplate(id) {
  if (!confirm('删除这个导入模板？不会影响已完成的导入。')) return;
  try { await api(`/api/import-templates/${id}`, {method:'DELETE'}); toast('导入模板已删除'); await loadImportTemplates(); } catch (errorObject) { toast(errorObject.message, true); }
}

function normalizeExportField(value) {
  const text = String(value || '').trim();
  if (importableStudentFields.includes(text)) return text;
  return importableStudentFields.find((field) => fieldLabel(field) === text) || null;
}

async function loadExportTemplates() {
  if (!hasCapability('student_export')) return;
  const templates = await api('/api/export-templates');
  state.exportTemplates = templates;
  const reportSelect = document.querySelector('#report-export-template');
  if (reportSelect) {
    const selected = reportSelect.value;
    reportSelect.innerHTML = `<option value="">当前筛选条件</option>${templates.map((template) => `<option value="${template.id}">${escapeHTML(template.name)}</option>`).join('')}`;
    reportSelect.value = templates.some((template) => String(template.id) === selected) ? selected : '';
  }
  if (state.user?.role !== 'super_admin') return;
  const body = document.querySelector('#export-templates-table');
  body.innerHTML = templates.length ? templates.map((template) => `<tr><td><strong>${escapeHTML(template.name)}</strong><span class="subline">${template.include_provenance ? '附带来源工作表' : '不附带来源工作表'}</span></td><td>${escapeHTML((template.fields || []).map(fieldLabel).join('、') || '全部字段')}</td><td>${escapeHTML(Object.entries(template.filters || {}).map(([key, value]) => `${fieldLabel(key)}：${value}`).join('；') || '无')}</td><td>${template.mask_sensitive ? '脱敏' : '原值'}</td><td>${dateTime(template.updated_at)}</td><td class="action-cell"><button class="icon-button" title="查看模板版本" data-template-history-kind="export" data-template-history-id="${template.id}" data-template-history-name="${escapeHTML(template.name)}"><i data-lucide="history"></i></button><button class="icon-button danger-icon" title="删除模板" data-delete-export-template="${template.id}"><i data-lucide="trash-2"></i></button></td></tr>`).join('') : '<tr><td colspan="6">尚无导出模板</td></tr>';
  body.querySelectorAll('[data-delete-export-template]').forEach((button) => button.addEventListener('click', () => deleteExportTemplate(Number(button.dataset.deleteExportTemplate))));
  body.querySelectorAll('[data-template-history-kind]').forEach((button) => button.addEventListener('click', () => openTemplateHistory(button.dataset.templateHistoryKind, Number(button.dataset.templateHistoryId), button.dataset.templateHistoryName)));
  refreshIcons();
}

async function saveExportTemplate(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const fields = form.elements.fields.value.split(/[,，]/).map(normalizeExportField).filter(Boolean);
  let filters = {};
  try { filters = form.elements.filters_json.value.trim() ? JSON.parse(form.elements.filters_json.value.trim()) : {}; } catch (_) { toast('固定筛选必须是合法 JSON。', true); return; }
  if (!filters || Array.isArray(filters) || typeof filters !== 'object') { toast('固定筛选必须是 JSON 对象。', true); return; }
  try {
    await api('/api/export-templates', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:form.elements.name.value, fields, filters, include_provenance:Boolean(form.elements.include_provenance.checked), mask_sensitive:Boolean(form.elements.mask_sensitive.checked)})});
    form.reset();
    form.elements.include_provenance.checked = true;
    toast('导出模板已保存');
    await loadExportTemplates();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function deleteExportTemplate(id) {
  if (!confirm('删除这个导出模板？不会删除任何学生数据或已导出文件。')) return;
  try { await api(`/api/export-templates/${id}`, {method:'DELETE'}); toast('导出模板已删除'); await loadExportTemplates(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function exportTemplate(id) {
  const data = await api(`/api/export-templates/${id}/export`, {method:'POST'});
  const task = data.task?.id ? await waitForTask(data.task.id) : data;
  if (task.result?.download_url) window.location.assign(task.result.download_url);
}

async function openTemplateHistory(kind, id, name) {
  try {
    const revisions = await api(`/api/template-revisions/${encodeURIComponent(kind)}/${id}`);
    document.querySelector('#template-history-title').textContent = `${name}的模板版本`;
    const list = document.querySelector('#template-history-list');
    const actionLabels = {created:'创建', updated:'保存更新', deleted:'删除前快照'};
    list.innerHTML = revisions.length ? revisions.map((revision) => `<article class="source-row template-history-row"><strong>版本 ${revision.revision_no} · ${escapeHTML(actionLabels[revision.action] || revision.action)}</strong><div class="source-meta"><span>${escapeHTML(revision.created_by)}</span><span class="source-time">${dateTime(revision.created_at)}</span></div><pre class="template-history-snapshot">${escapeHTML(JSON.stringify(revision.snapshot || {}, null, 2))}</pre></article>`).join('') : '<p class="source-empty">尚无模板版本记录。</p>';
    document.querySelector('#template-history-dialog').showModal();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadDataScopes() {
  if (!['super_admin', 'admin'].includes(state.user?.role)) return;
  const accounts = await api('/api/system/data-scopes');
  const body = document.querySelector('#data-scopes-table');
  body.innerHTML = accounts.length ? accounts.map((account) => `<tr><td><strong>${escapeHTML(account.display_name || account.username)}</strong><span class="subline">${escapeHTML(account.username)}</span></td><td>${escapeHTML(account.role)}</td><td>${escapeHTML(formatScopeRules(account.scope || [], account.scope_mode))}</td><td class="action-cell"><button class="icon-button" title="配置数据范围" data-edit-scope="${account.id}"><i data-lucide="sliders-horizontal"></i></button></td></tr>`).join('') : '<tr><td colspan="4">尚无可配置账号</td></tr>';
  body.querySelectorAll('[data-edit-scope]').forEach((button) => button.addEventListener('click', () => openDataScopeDialog(accounts.find((item) => item.id === Number(button.dataset.editScope)))));
  refreshIcons();
}

function formatScopeRules(rules, mode = '') {
  if (mode === 'unconfigured') return '未配置（教师不可访问）';
  if (mode === 'all') return '全部学生';
  const values = Array.isArray(rules) ? rules : [rules];
  return values.map((rule) => Object.entries(rule || {}).map(([key, value]) => `${fieldLabel(key)}：${value}`).join('，')).filter(Boolean).join('；') || '未限制';
}

const dataScopeFields = [
  ['school', '所属学校', '全部学校'],
  ['college', '所属学院', '全部学院'],
  ['school_major', '学校专业', '全部专业'],
  ['current_class', '所在班级', '全部班级'],
];

function scopeRuleValues(row) {
  return Object.fromEntries(dataScopeFields.map(([field]) => [field, row.querySelector(`[data-scope-field="${field}"]`)?.value || '']));
}

function dataScopeRulesFromDialog() {
  return [...document.querySelectorAll('#data-scope-rules .data-scope-rule')].map(scopeRuleValues).filter((rule) => Object.values(rule).some(Boolean));
}

function scheduleDataScopePreview() {
  window.clearTimeout(state.dataScopePreviewTimer);
  state.dataScopePreviewTimer = window.setTimeout(() => updateDataScopePreview(), 180);
}

async function updateDataScopePreview(rulesOverride = null) {
  const dialog = document.querySelector('#data-scope-dialog');
  if (!dialog.open || !dialog.dataset.accountId) return;
  const requestId = ++state.dataScopePreviewRequest;
  const preview = document.querySelector('#data-scope-preview');
  preview.textContent = '正在计算当前范围覆盖的学生数量...';
  try {
    const result = await api(`/api/system/users/${dialog.dataset.accountId}/data-scope/preview`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rules:rulesOverride || dataScopeRulesFromDialog()})});
    if (requestId !== state.dataScopePreviewRequest || !dialog.open) return;
    const samples = result.samples?.length ? result.samples.map((item) => `${escapeHTML(item.full_name)}（${escapeHTML(item.student_no)}）`).join('、') : '暂无匹配学生';
    const counts = result.dimension_counts || {};
    preview.innerHTML = `<strong>将覆盖 ${result.total_students} 名学生</strong><span>学校 ${counts.schools || 0} 个 · 学院 ${counts.colleges || 0} 个 · 专业 ${counts.majors || 0} 个 · 班级 ${counts.classes || 0} 个</span><span>样本：${samples}</span>`;
  } catch (errorObject) {
    if (requestId === state.dataScopePreviewRequest) preview.textContent = errorObject.message;
  }
}

function setScopeSelectOptions(select, values, emptyLabel, selected = '') {
  const options = selected && !values.includes(selected) ? [selected, ...values] : values;
  select.innerHTML = `<option value="">${escapeHTML(emptyLabel)}</option>${options.map((value) => `<option value="${escapeHTML(value)}">${escapeHTML(value)}</option>`).join('')}`;
  select.value = options.includes(selected) ? selected : '';
}

async function loadDataScopeRuleOptions(row, selectedValues = null) {
  const current = selectedValues || scopeRuleValues(row);
  const params = new URLSearchParams();
  if (current.school) params.set('school', current.school);
  if (current.college) params.set('college', current.college);
  if (current.school_major) params.set('school_major', current.school_major);
  const data = await api(`/api/students/filter-options?${params.toString()}`);
  const values = {
    school: data.schools || [],
    college: data.colleges || [],
    school_major: data.majors || [],
    current_class: data.classes || [],
  };
  dataScopeFields.forEach(([field, , emptyLabel]) => setScopeSelectOptions(row.querySelector(`[data-scope-field="${field}"]`), values[field], emptyLabel, current[field] || ''));
}

function addDataScopeRule(rule = {}, refreshPreview = true) {
  const container = document.querySelector('#data-scope-rules');
  const row = document.createElement('article');
  row.className = 'data-scope-rule';
  row.innerHTML = `<div class="data-scope-rule-head"><strong>范围规则</strong><button class="icon-button danger-icon" type="button" data-remove-scope-rule title="移除这条规则"><i data-lucide="trash-2"></i></button></div><div class="data-scope-rule-grid">${dataScopeFields.map(([field, label, emptyLabel]) => `<label>${label}<select data-scope-field="${field}"><option value="">${emptyLabel}</option></select></label>`).join('')}</div>`;
  container.append(row);
  row.querySelector('[data-remove-scope-rule]').addEventListener('click', () => {
    if (container.children.length === 1) {
      dataScopeFields.forEach(([field]) => { row.querySelector(`[data-scope-field="${field}"]`).value = ''; });
      loadDataScopeRuleOptions(row).then(scheduleDataScopePreview).catch((errorObject) => toast(errorObject.message, true));
      return;
    }
    row.remove();
    scheduleDataScopePreview();
  });
  row.querySelectorAll('[data-scope-field]').forEach((select) => select.addEventListener('change', async (event) => {
    const field = event.target.dataset.scopeField;
    const descendants = field === 'school' ? ['college', 'school_major', 'current_class'] : field === 'college' ? ['school_major', 'current_class'] : field === 'school_major' ? ['current_class'] : [];
    descendants.forEach((descendant) => { row.querySelector(`[data-scope-field="${descendant}"]`).value = ''; });
    try { await loadDataScopeRuleOptions(row); scheduleDataScopePreview(); } catch (errorObject) { toast(errorObject.message, true); }
  }));
  loadDataScopeRuleOptions(row, Object.fromEntries(dataScopeFields.map(([field]) => [field, rule[field] || '']))).then(() => { if (refreshPreview) scheduleDataScopePreview(); }).catch((errorObject) => toast(errorObject.message, true));
  refreshIcons();
}

function openDataScopeDialog(account) {
  if (!account) return;
  const dialog = document.querySelector('#data-scope-dialog');
  dialog.dataset.accountId = String(account.id);
  document.querySelector('#data-scope-account').innerHTML = `<strong>${escapeHTML(account.display_name || account.username)}</strong><span class="subline">${escapeHTML(account.username)} · ${escapeHTML(account.role)}</span>`;
  const container = document.querySelector('#data-scope-rules');
  container.innerHTML = '';
  const rules = Array.isArray(account.scope) && account.scope.length ? account.scope : [{}];
  rules.forEach((rule) => addDataScopeRule(rule, false));
  dialog.showModal();
  updateDataScopePreview(rules);
  refreshIcons();
}

async function saveDataScope(event) {
  event.preventDefault();
  const dialog = document.querySelector('#data-scope-dialog');
  const accountId = Number(dialog.dataset.accountId);
  const rules = dataScopeRulesFromDialog();
  try {
    await api(`/api/system/users/${accountId}/data-scope`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({rules})});
    dialog.close();
    toast('账号数据范围已保存');
    await loadDataScopes();
  } catch (errorObject) { toast(errorObject.message, true); }
}

function qualitySeverityLabel(severity) { return ({high:'高', medium:'中', low:'低'})[severity] || severity; }

async function loadOperations() {
  if (!['super_admin', 'admin'].includes(state.user?.role)) return;
  const sourceSection = document.querySelector('#source-documents-section');
  if (sourceSection) sourceSection.hidden = !hasCapability('source_manage');
  const hasQualityAccess = hasCapability('quality_manage');
  ['#quality-metric', '#quality-center-section', '#student-reminders-section', '#duplicate-students-section'].forEach((selector) => {
    const node = document.querySelector(selector);
    if (node) node.hidden = !hasQualityAccess;
  });
  const tasks = [loadMonitoring(), loadTasks(), loadAlerts(), loadAiEvaluation(), loadRecycleBin()];
  if (hasQualityAccess) tasks.push(loadQualityScan(), loadStudentReminders(), loadDuplicateStudents());
  if (hasCapability('source_manage')) tasks.push(loadDocuments());
  await Promise.all(tasks);
}

async function loadQualityScan(run = false) {
  const data = await api(run ? '/api/quality-scans' : '/api/quality-scans/latest', run ? {method:'POST'} : {});
  document.querySelector('#quality-total').textContent = data.summary?.total_issues ?? '-';
  const target = document.querySelector('#quality-issues');
  target.innerHTML = (data.issues || []).map((issue) => {
    const students = issue.students || [];
    const actions = students.filter((student) => student.case_id && student.case_status === 'open').slice(0, 3).map((student) => `<button class="text-button" data-resolve-quality="${student.case_id}">${escapeHTML(student.student_no)} ${escapeHTML(student.full_name)}</button>`).join('');
    return `<article class="quality-issue severity-${escapeHTML(issue.severity)}"><div><span class="status ${issue.severity === 'high' ? 'error' : issue.severity === 'medium' ? 'pending' : 'muted'}">${qualitySeverityLabel(issue.severity)}</span><h3>${escapeHTML(issue.label)}</h3></div><strong>${issue.count}</strong><p>${issue.count ? escapeHTML(students.slice(0, 3).map((student) => `${student.student_no} ${student.full_name}`).join('；')) : '未发现问题'}</p>${actions ? `<div class="quality-actions">${actions}</div>` : ''}</article>`;
  }).join('') || '<p class="source-empty">尚无质量检查结果。</p>';
  target.querySelectorAll('[data-resolve-quality]').forEach((button) => button.addEventListener('click', () => resolveQualityIssue(Number(button.dataset.resolveQuality))));
}

async function resolveQualityIssue(caseId) {
  const note = window.prompt('填写处理说明，可留空：', '已核对并处理');
  if (note === null) return;
  try { await api(`/api/quality-issues/${caseId}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:'resolved', note})}); toast('质量问题已标记为解决'); await loadQualityScan(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadStudentReminders() {
  const reminders = await api('/api/student-reminders?limit=100');
  const target = document.querySelector('#student-reminders');
  target.innerHTML = reminders.length ? reminders.map((item) => `<article class="reminder-row severity-${escapeHTML(item.severity)}"><div><span class="status ${item.severity === 'medium' ? 'pending' : 'muted'}">${escapeHTML(item.severity === 'medium' ? '提示' : '待核对')}</span><strong>${escapeHTML(item.full_name)} · ${escapeHTML(item.title)}</strong><p>${escapeHTML(item.student_no)}${item.current_class ? ` · ${escapeHTML(item.current_class)}` : ''}　${escapeHTML(item.detail)}</p></div><button class="icon-button" title="定位学生" data-reminder-student="${item.student_id}" data-reminder-no="${escapeHTML(item.student_no)}"><i data-lucide="external-link"></i></button></article>`).join('') : '<p class="source-empty">当前没有需要跟进的学生提醒。</p>';
  target.querySelectorAll('[data-reminder-student]').forEach((button) => button.addEventListener('click', () => focusStudent(button.dataset.reminderNo)));
  refreshIcons();
}

async function focusStudent(studentNo) {
  setView('students');
  document.querySelector('#student-search').value = studentNo;
  state.studentPage = 1;
  await loadStudents();
}

async function loadDuplicateStudents() {
  const groups = await api('/api/students/duplicates');
  const target = document.querySelector('#duplicate-students');
  target.innerHTML = groups.length ? groups.map((group, index) => `<article class="duplicate-group"><div class="duplicate-group-head"><span class="status pending">${escapeHTML(group.match_type)}</span><strong>${group.count} 条候选档案</strong></div><div class="duplicate-student-grid">${group.students.map((student) => `<div class="duplicate-student"><strong>${escapeHTML(student.student_no)} · ${escapeHTML(student.full_name)}</strong><span>${escapeHTML([student.school_major, student.current_class].filter(Boolean).join(' · ') || '未填写专业/班级')}</span><button class="text-button" data-merge-target="${student.id}" data-duplicate-group="${index}">保留此档案并合并</button></div>`).join('')}</div></article>`).join('') : '<p class="source-empty">未发现需要人工合并的疑似重复档案。</p>';
  target.querySelectorAll('[data-merge-target]').forEach((button) => button.addEventListener('click', () => mergeDuplicateStudent(Number(button.dataset.mergeTarget), groups[Number(button.dataset.duplicateGroup)]?.students || [])));
}

async function mergeDuplicateStudent(targetStudentId, candidates) {
  const target = candidates.find((item) => item.id === targetStudentId);
  const choices = candidates.filter((item) => item.id !== targetStudentId);
  if (!target || !choices.length) return;
  const sourceId = Number(window.prompt(`保留 ${target.student_no} · ${target.full_name}。请输入需要合并进去的学生 ID：\n${choices.map((item) => `${item.id}: ${item.student_no} · ${item.full_name}`).join('\n')}`, String(choices[0].id)));
  if (!choices.some((item) => item.id === sourceId)) return;
  if (!confirm('合并会把源档案中目标档案为空的字段、来源记录与相关信息词条转入保留档案，并保留源档案快照。继续二次确认？')) return;
  if (window.prompt('二次确认：请输入“合并学生”继续：') !== '合并学生') return;
  try {
    const result = await api(`/api/students/${sourceId}/merge`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({target_student_id:targetStudentId, confirmation_phrase:'合并学生'})});
    toast(result.message || '学生档案已合并');
    await Promise.all([loadDuplicateStudents(), loadQualityScan(), loadStudents(), loadDashboard()]);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadMonitoring() {
  const data = await api('/api/system/monitoring');
  document.querySelector('#ops-db-size').textContent = formatBytes(data.database?.size_bytes);
  document.querySelector('#ops-ai-latency').textContent = data.ai?.available ? `${data.ai.health_probe_ms} ms` : '降级';
  document.querySelector('#ops-failed-tasks').textContent = data.tasks?.failed ?? '-';
  const gpu = data.gpu?.available ? (data.gpu.gpus || []).map((item) => item.join(' · ')).join('；') : '未检测到 NVIDIA GPU';
  document.querySelector('#monitoring-details').innerHTML = `<article><span>磁盘可用</span><strong>${formatBytes(data.disk?.free)}</strong><p>已用 ${formatBytes(data.disk?.used)} / ${formatBytes(data.disk?.total)}</p></article><article><span>最近备份</span><strong>${escapeHTML(data.latest_backup?.validation_status || data.latest_backup?.status || '无')}</strong><p>${escapeHTML(data.latest_backup?.file_name || '尚未生成')}</p></article><article><span>本地 AI</span><strong>${escapeHTML(data.ai?.detail || '未知')}</strong><p>${escapeHTML(data.ai?.model || '')}</p></article><article><span>CUDA / 显卡</span><strong>${escapeHTML(gpu)}</strong><p>任务：等待 ${data.tasks?.queued || 0}，执行中 ${data.tasks?.running || 0}</p></article>`;
}

async function loadAlerts() {
  const alerts = await api('/api/system/alerts');
  const target = document.querySelector('#system-alerts');
  target.innerHTML = alerts.length ? alerts.map((alert) => `<article class="system-alert severity-${escapeHTML(alert.severity)}"><div><span class="status ${alert.severity === 'high' ? 'error' : 'pending'}">${escapeHTML(alert.severity)}</span><h3>${escapeHTML(alert.title)}</h3><p>${escapeHTML(alert.detail)}</p><small>最近检测：${dateTime(alert.last_seen_at)}</small></div>${alert.status === 'open' ? `<button class="button subtle" data-ack-alert="${alert.id}">确认已知</button>` : '<span class="status muted">已确认</span>'}</article>`).join('') : '<p class="source-empty">当前没有开放告警。</p>';
  target.querySelectorAll('[data-ack-alert]').forEach((button) => button.addEventListener('click', () => acknowledgeAlert(Number(button.dataset.ackAlert))));
}

async function checkAlerts() {
  try { await api('/api/system/alerts/check', {method:'POST'}); toast('系统告警已检查'); await Promise.all([loadAlerts(), loadMonitoring()]); } catch (errorObject) { toast(errorObject.message, true); }
}

async function acknowledgeAlert(id) {
  try { await api(`/api/system/alerts/${id}/acknowledge`, {method:'POST'}); toast('告警已确认'); await loadAlerts(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadAiEvaluation() {
  const data = await api('/api/system/ai-evaluations/latest');
  const target = document.querySelector('#ai-evaluation');
  if (!data) { target.innerHTML = '<p class="source-empty">尚未运行 AI 可靠性检查。</p>'; return; }
  const results = (data.results || []).map((item) => `<article class="evaluation-row"><span class="status ${item.passed ? 'success' : 'error'}">${item.passed ? '通过' : '失败'}</span><strong>${escapeHTML(item.title)}</strong><span>${escapeHTML(item.intent)}</span><span>${escapeHTML(item.detail)}</span></article>`).join('') || '<p class="source-empty">本次检查没有返回明细。</p>';
  target.innerHTML = `<article class="evaluation-summary"><strong>${escapeHTML(data.status === 'completed' ? `${data.summary?.passed || 0} / ${data.summary?.total || 0} 通过` : '服务降级')}</strong><span>${escapeHTML(data.summary?.model || '')}</span><time>${dateTime(data.created_at)}</time></article><div class="evaluation-results">${results}</div>`;
}

async function runAiEvaluation() {
  try { const data = await api('/api/system/ai-evaluations', {method:'POST'}); toast(`AI 检查已进入后台任务 #${data.task?.id || ''}`); await loadTasks(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadDocuments() {
  const documents = await api('/api/documents');
  const body = document.querySelector('#documents-table');
  body.innerHTML = documents.length ? documents.map((document) => `<tr><td><a href="/api/documents/${document.id}/download">${escapeHTML(document.filename)}</a><span class="subline">${escapeHTML(document.file_type)} · ${formatBytes(document.size_bytes)}</span></td><td>第 ${document.version_no || 1} 版<span class="subline">${escapeHTML((document.tags || []).join('、') || '无标签')}</span></td><td>${document.import_count} 次导入 / ${document.related_card_count} 个词条<span class="subline">关联学生 ${document.associated_student_count || 0} 人</span></td><td>${statusTag(document.status === 'archived' ? 'inactive' : 'active')}</td><td>${dateTime(document.uploaded_at)}</td><td class="action-cell"><button class="icon-button" title="编辑标签" data-edit-document="${document.id}"><i data-lucide="tags"></i></button><button class="icon-button" title="${document.status === 'archived' ? '取消归档' : '归档'}" data-toggle-document="${document.id}"><i data-lucide="archive"></i></button>${document.related_card_count ? `<button class="icon-button danger-icon" title="删除该来源写入的全部词条" data-rollback-document="${document.id}"><i data-lucide="undo-2"></i></button>` : ''}<button class="icon-button danger-icon" title="删除原始文件及关联学生" data-delete-document="${document.id}"><i data-lucide="trash-2"></i></button></td></tr>`).join('') : '<tr><td colspan="6">尚无原始资料</td></tr>';
  body.querySelectorAll('[data-edit-document]').forEach((button) => button.addEventListener('click', () => editDocument(documents.find((item) => item.id === Number(button.dataset.editDocument)))));
  body.querySelectorAll('[data-toggle-document]').forEach((button) => button.addEventListener('click', () => toggleDocumentArchive(documents.find((item) => item.id === Number(button.dataset.toggleDocument)))));
  body.querySelectorAll('[data-rollback-document]').forEach((button) => button.addEventListener('click', () => rollbackDocumentCards(documents.find((item) => item.id === Number(button.dataset.rollbackDocument)))));
  body.querySelectorAll('[data-delete-document]').forEach((button) => button.addEventListener('click', () => deleteSourceDocument(documents.find((item) => item.id === Number(button.dataset.deleteDocument)))));
  refreshIcons();
}

async function editDocument(document) {
  const raw = window.prompt('用逗号分隔文件标签：', (document.tags || []).join(','));
  if (raw === null) return;
  try { await api(`/api/documents/${document.id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tags: raw.split(/[,，]/).map((item) => item.trim()).filter(Boolean)})}); toast('文件标签已保存'); await loadDocuments(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function toggleDocumentArchive(document) {
  const status = document.status === 'archived' ? 'active' : 'archived';
  if (!confirm(status === 'archived' ? '归档后仍保留原始文件和已有数据，确认继续？' : '确认取消归档？')) return;
  try { await api(`/api/documents/${document.id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status})}); toast(status === 'archived' ? '文件已归档' : '文件已恢复'); await loadDocuments(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function rollbackDocumentCards(document) {
  if (!confirm(`确认删除“${document.filename}”写入的 ${document.related_card_count} 个词条？不会删除原始文件或学生主体档案。`)) return;
  try { const data = await api(`/api/documents/${document.id}/related-info-cards`, {method:'DELETE'}); toast(`已删除 ${data.deleted_cards} 个来源词条`); await Promise.all([loadDocuments(), loadStudents()]); } catch (errorObject) { toast(errorObject.message, true); }
}

async function deleteSourceDocument(document) {
  if (!document) return;
  if (!confirm(`第一次确认：删除“${document.filename}”会永久移除原始 ${document.file_type === 'word' ? 'Word' : 'Excel'} 文件，并删除关联的 ${document.associated_student_count || 0} 名学生档案。继续？`)) return;
  if (!confirm('第二次确认：关联学生会移入回收站，学生字段来源、相关词条和待审核内容也会一并处理；操作审计仍会保留。确认继续？')) return;
  if (window.prompt('第三次确认：请输入“永久删除原始资料”继续：') !== '永久删除原始资料') return;
  try {
    const data = await api(`/api/documents/${document.id}`, {
      method:'DELETE',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({confirmation_count:3, confirmation_phrase:'永久删除原始资料'}),
    });
    toast(`原始资料已删除，已处理 ${data.deleted_students || 0} 名关联学生`);
    await Promise.all([loadDocuments(), loadStudents(), loadDashboard(), loadRecycleBin()]);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadRecycleBin() {
  const rows = await api('/api/recycle-bin');
  const body = document.querySelector('#recycle-bin-table');
  body.innerHTML = rows.length ? rows.map((row) => `<tr><td><strong>${escapeHTML(row.student_no)}</strong><span class="subline">${escapeHTML(row.full_name)}</span></td><td>${dateTime(row.deleted_at)}</td><td>${dateTime(row.expires_at)}</td><td>${row.related_card_count || 0}</td><td class="action-cell"><button class="icon-button" title="恢复学生" data-restore-recycle="${row.id}"><i data-lucide="rotate-ccw"></i></button>${state.user?.role === 'super_admin' ? `<button class="icon-button danger-icon" title="彻底清除" data-purge-recycle="${row.id}"><i data-lucide="trash-2"></i></button>` : ''}</td></tr>`).join('') : '<tr><td colspan="5">回收站为空</td></tr>';
  body.querySelectorAll('[data-restore-recycle]').forEach((button) => button.addEventListener('click', () => restoreRecycleStudent(Number(button.dataset.restoreRecycle))));
  body.querySelectorAll('[data-purge-recycle]').forEach((button) => button.addEventListener('click', () => purgeRecycleStudent(Number(button.dataset.purgeRecycle))));
  refreshIcons();
}

async function restoreRecycleStudent(id) {
  if (!confirm('确认恢复这名学生及其相关信息词条？')) return;
  try { await api(`/api/recycle-bin/${id}/restore`, {method:'POST'}); toast('学生档案已恢复'); await Promise.all([loadRecycleBin(), loadStudents(), loadDashboard()]); } catch (errorObject) { toast(errorObject.message, true); }
}

async function purgeRecycleStudent(id) {
  if (window.prompt('彻底清除不可恢复。请输入“彻底清除”继续：') !== '彻底清除') return;
  try { await api(`/api/recycle-bin/${id}`, {method:'DELETE'}); toast('回收站记录已彻底清除'); await loadRecycleBin(); } catch (errorObject) { toast(errorObject.message, true); }
}

async function loadTasks() {
  const tasks = await api('/api/tasks');
  const body = document.querySelector('#tasks-table');
  body.innerHTML = tasks.length ? tasks.map((task) => `<tr><td>${escapeHTML(task.task_type)}</td><td>${statusTag(task.status)}</td><td>${task.progress}%</td><td>${escapeHTML(task.error_message || task.result?.filename || task.message || '-')} ${task.result?.download_url ? `<a href="${escapeHTML(task.result.download_url)}">下载 XLSX</a>` : ''}</td><td>${dateTime(task.created_at)}</td></tr>`).join('') : '<tr><td colspan="5">没有后台任务</td></tr>';
}

function auditSummary(record) {
  const data = record.after || record.before || {};
  if (data.question) return `问题：${data.question}`;
  if (data.document) return `文件：${data.document}`;
  if (data.filters) return `筛选：${Object.entries(data.filters).filter(([, value]) => value).map(([key, value]) => `${fieldLabel(key)}=${value}`).join('；') || '全部'}`;
  return Object.keys(data).length ? JSON.stringify(data) : '-';
}

async function loadAuditView() {
  if (!['super_admin', 'admin'].includes(state.user?.role)) return;
  await Promise.all([loadAiConversationLogs(), loadLoginSecurityEvents(), loadAuditLogs()]);
}

async function loadAiConversationLogs() {
  const conversations = await api('/api/ai/admin/conversations?per_user_limit=10');
  const body = document.querySelector('#ai-conversations-table');
  body.innerHTML = conversations.length ? conversations.map((conversation) => `<tr><td><strong>${escapeHTML(conversation.user)}</strong><span class="subline">${escapeHTML(conversation.username)}</span></td><td><span class="ai-log-question">${escapeHTML(conversation.question || '-')}</span></td><td><span class="ai-log-answer">${escapeHTML(conversation.reply || '-')}</span></td><td>${dateTime(conversation.updated_at)}</td><td class="action-cell"><button class="icon-button" data-ai-log-id="${escapeHTML(conversation.id)}" title="查看完整对话"><i data-lucide="message-square-text"></i></button></td></tr>`).join('') : '<tr><td colspan="5">尚无 AI 对话记录</td></tr>';
  body.querySelectorAll('[data-ai-log-id]').forEach((button) => button.addEventListener('click', () => openAiLog(button.dataset.aiLogId)));
  refreshIcons();
}

async function openAiLog(conversationId) {
  const data = await api(`/api/ai/admin/conversations/${encodeURIComponent(conversationId)}`);
  document.querySelector('#ai-log-dialog-title').textContent = `${data.user}的 AI 对话`;
  const list = document.querySelector('#ai-log-list');
  list.innerHTML = data.messages.length ? data.messages.map((message) => `<article class="ai-log-message ${escapeHTML(message.role)}"><strong>${message.role === 'user' ? '提问' : 'AI 输出'} · ${dateTime(message.created_at)}${message.role === 'assistant' && message.duration_ms != null ? ` · ${escapeHTML(message.model_name || '本地模型')} · ${message.duration_ms} ms` : ''}</strong><p>${escapeHTML(message.content)}</p>${renderAiSources(message.sources || [])}</article>`).join('') : '<p class="source-empty">没有对话内容。</p>';
  document.querySelector('#ai-log-dialog').showModal();
}

async function loadAuditLogs() {
  const form = document.querySelector('#audit-filters');
  const data = form ? new FormData(form) : new FormData();
  const params = new URLSearchParams({limit:'200'});
  ['action', 'entity_type'].forEach((key) => { const value = String(data.get(key) || '').trim(); if (value) params.set(key, value); });
  const records = await api(`/api/audit?${params.toString()}`);
  const body = document.querySelector('#audit-table');
  body.innerHTML = records.length ? records.map((record) => {
    const undo = record.can_undo ? `<button class="text-button audit-undo-button" type="button" data-undo-audit="${record.id}">撤回</button>` : record.undone ? '<span class="subline">已撤回</span>' : '';
    return `<tr><td>${dateTime(record.created_at)}</td><td>${escapeHTML(record.actor)}</td><td>${escapeHTML(record.action)}</td><td>${escapeHTML(record.entity_type)} / ${escapeHTML(record.entity_id)}</td><td><span class="audit-detail" title="${escapeHTML(auditSummary(record))}">${escapeHTML(auditSummary(record))}</span></td><td class="action-cell">${undo}</td></tr>`;
  }).join('') : '<tr><td colspan="6">尚无操作审计记录</td></tr>';
  body.querySelectorAll('[data-undo-audit]').forEach((button) => button.addEventListener('click', () => undoAuditChange(Number(button.dataset.undoAudit), button)));
}

async function loadLoginSecurityEvents() {
  const events = await api('/api/auth/login-security-events?limit=100');
  const body = document.querySelector('#login-security-table');
  const labels = {login_success:'登录成功', login_failed:'密码错误', login_mfa_failed:'二次验证失败', login_locked:'登录已锁定'};
  body.innerHTML = events.length ? events.map((event) => `<tr><td>${dateTime(event.created_at)}</td><td><strong>${escapeHTML(event.display_name || event.username)}</strong><span class="subline">${escapeHTML(event.username)}</span></td><td>${event.is_unusual ? '<span class="status pending">网络变化</span>' : `<span class="status ${event.event_type === 'login_success' ? 'success' : 'error'}">${escapeHTML(labels[event.event_type] || event.event_type)}</span>`}</td><td>${escapeHTML(event.ip_address || '-')}</td><td>${escapeHTML(event.network_key || '-')}</td><td>${escapeHTML(event.device_label || '-')}</td></tr>`).join('') : '<tr><td colspan="6">尚无登录安全记录</td></tr>';
}

async function undoAuditChange(auditId, button) {
  if (!window.confirm('确认撤回这条数据库改动？系统会先校验目标记录是否仍处于原改动后的状态，并保留新的撤回审计记录。')) return;
  button.disabled = true;
  try {
    await api(`/api/audit/${auditId}/undo`, {method:'POST'});
    toast('数据库改动已撤回');
    const refreshes = [loadAuditLogs(), loadStudents(), loadDashboard(), loadImports(), loadRecycleBin()];
    if (hasCapability('source_manage')) refreshes.push(loadDocuments());
    await Promise.all(refreshes);
  } catch (errorObject) {
    button.disabled = false;
    toast(errorObject.message, true);
  }
}

async function verifyAudit() {
  try {
    const result = await api('/api/audit/verify');
    toast(result.valid ? `审计链校验通过，已核对 ${result.checked} 条记录` : `审计链异常，首次异常记录 #${result.failed_id}`, !result.valid);
  } catch (errorObject) { toast(errorObject.message, true); }
}

function applyDefaultAdministratorPermissions(role) {
  const form = document.querySelector('#administrator-form');
  const defaults = role === 'admin'
    ? ['student_edit', 'student_export', 'related_review', 'source_manage', 'quality_manage', 'audit_view']
    : ['student_edit', 'student_export', 'related_review'];
  form.querySelectorAll('input[name="permissions"]').forEach((input) => { input.checked = defaults.includes(input.value); });
}

function openAdministratorDialog(id = null) {
  const form = document.querySelector('#administrator-form');
  const password = form.elements.password;
  const confirmation = form.elements.confirm_password;
  state.currentAdministrator = id ? state.administrators.find((item) => item.id === id) : null;
  form.reset();
  document.querySelector('#administrator-form-error').textContent = '';

  if (state.currentAdministrator) {
    document.querySelector('#administrator-dialog-title').textContent = '编辑账号';
    document.querySelector('#administrator-submit-label').textContent = '保存更改';
    document.querySelector('#administrator-password-label').textContent = '新密码（留空则不重置）';
    document.querySelector('#administrator-confirm-password-label').textContent = '确认新密码';
    form.elements.username.value = state.currentAdministrator.username;
    form.elements.display_name.value = state.currentAdministrator.display_name;
    form.elements.role.value = state.currentAdministrator.role || 'admin';
    form.querySelectorAll('input[name="permissions"]').forEach((input) => { input.checked = Boolean(state.currentAdministrator.permissions?.includes(input.value)); });
    password.required = false;
    confirmation.required = false;
  } else {
    document.querySelector('#administrator-dialog-title').textContent = '新增账号';
    document.querySelector('#administrator-submit-label').textContent = '创建账号';
    document.querySelector('#administrator-password-label').textContent = '账号密码';
    document.querySelector('#administrator-confirm-password-label').textContent = '确认密码';
    password.required = true;
    confirmation.required = true;
    applyDefaultAdministratorPermissions('admin');
  }
  const isOrdinaryAdmin = state.user?.role === 'admin';
  const roleLabel = form.elements.role.closest('label');
  const administratorOption = form.elements.role.querySelector('option[value="admin"]');
  roleLabel.hidden = isOrdinaryAdmin;
  if (administratorOption) {
    administratorOption.hidden = isOrdinaryAdmin;
    administratorOption.disabled = isOrdinaryAdmin;
  }
  if (isOrdinaryAdmin) form.elements.role.value = 'teacher';
  if (!state.currentAdministrator) applyDefaultAdministratorPermissions(form.elements.role.value);
  const currentPasswordLabel = form.elements.current_password.closest('label');
  if (currentPasswordLabel?.firstChild) currentPasswordLabel.firstChild.textContent = isOrdinaryAdmin ? '管理员当前密码' : '超级管理员当前密码';
  document.querySelector('#administrator-dialog').showModal();
}

async function saveAdministrator(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#administrator-form-error');
  error.textContent = '';
  const payload = Object.fromEntries(new FormData(form).entries());
  const configuredPermissions = Array.from(form.querySelectorAll('input[name="permissions"]:checked')).map((input) => input.value);
  payload.permissions = configuredPermissions.length ? configuredPermissions : null;
  if (state.currentAdministrator) {
    payload.new_password = payload.password || null;
    delete payload.password;
    if (!payload.new_password) payload.confirm_password = null;
  }
  try {
    const path = state.currentAdministrator ? `/api/system/administrators/${state.currentAdministrator.id}` : '/api/system/administrators';
    await api(path, {method: state.currentAdministrator ? 'PUT' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    document.querySelector('#administrator-dialog').close();
    toast(state.currentAdministrator ? '账号已更新' : (state.user?.role === 'admin' ? '教师账号已创建' : '普通账号已创建'));
    await loadAdministrators();
  } catch (errorObject) {
    error.textContent = errorObject.message;
  }
}

async function revokeAdministratorSessions(administratorId) {
  const account = state.administrators.find((item) => item.id === administratorId);
  if (!account) return;
  if (!confirm(`确认强制注销“${account.display_name || account.username}”的全部已登录会话？该账号需要重新登录。`)) return;
  const currentPassword = window.prompt(`请输入${state.user?.role === 'admin' ? '管理员' : '超级管理员'}当前密码：`);
  if (!currentPassword) return;
  if (window.prompt('二次确认：请输入“注销会话”继续：') !== '注销会话') return;
  try {
    await api(`/api/system/users/${administratorId}/revoke-sessions`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({current_password:currentPassword, confirmation_phrase:'注销会话'})});
    toast('该账号的全部会话已注销');
  } catch (errorObject) { toast(errorObject.message, true); }
}

function openAccountSecurityDialog(forcePasswordChange = false) {
  const dialog = document.querySelector('#account-security-dialog');
  const form = document.querySelector('#account-security-form');
  form.reset();
  document.querySelector('#account-security-error').textContent = '';
  document.querySelector('#account-security-state').textContent = forcePasswordChange
    ? '此账号的密码由管理员创建或重置，请先设置只有您本人知道的新密码。'
    : (state.user?.mfa_enabled ? '二次验证已启用。登录时需要身份验证器生成的六码代码。' : '二次验证尚未启用。建议管理员和教师启用身份验证器保护账号。');
  document.querySelector('#disable-mfa-button').hidden = !state.user?.mfa_enabled;
  dialog.showModal();
}

async function saveOwnPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#account-security-error');
  error.textContent = '';
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    await api('/api/auth/password', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    // Password changes rotate the session token; reload so every page resource
    // and status panel is initialized against the new session.
    window.location.reload();
  } catch (errorObject) { error.textContent = errorObject.message; }
}

async function setupMfa() {
  try {
    const setup = await api('/api/auth/mfa/setup', {method:'POST'});
    const copied = window.prompt(`在身份验证器中添加手动密钥。账户：${setup.account}\n服务：${setup.issuer}\n密钥如下，请先复制保存：`, setup.secret);
    if (copied === null) return;
    const code = window.prompt('输入身份验证器当前显示的六码代码以启用：');
    if (!code) return;
    await api('/api/auth/mfa/enable', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code})});
    await loadUser();
    openAccountSecurityDialog(false);
    toast('二次验证已启用');
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function disableMfa() {
  const currentPassword = window.prompt('请输入当前密码：');
  if (!currentPassword) return;
  const code = window.prompt('请输入身份验证器当前显示的六码代码：');
  if (!code) return;
  try {
    await api('/api/auth/mfa/disable', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({current_password:currentPassword, code})});
    await loadUser();
    openAccountSecurityDialog(false);
    toast('二次验证已关闭');
  } catch (errorObject) { toast(errorObject.message, true); }
}

function excelSummaryHeader(payload, rowIndex, columnIndex) {
  const headerRows = Array.isArray(payload?.header_rows) ? payload.header_rows : [];
  const directValue = headerRows[rowIndex]?.[columnIndex];
  if (directValue) return String(directValue);
  const mergedRange = (payload?.merged_ranges || []).find((range) => (
    Number(range.start_row) <= rowIndex + 1
    && Number(range.end_row) >= rowIndex + 1
    && Number(range.start_column) <= columnIndex + 1
    && Number(range.end_column) >= columnIndex + 1
  ));
  if (!mergedRange) return '';
  return String(headerRows[Number(mergedRange.start_row) - 1]?.[Number(mergedRange.start_column) - 1] || '');
}

function excelRecordSummary(payload) {
  const headerRows = Array.isArray(payload?.header_rows) ? payload.header_rows : [];
  const dataRow = Array.isArray(payload?.data_row) ? payload.data_row : [];
  const values = dataRow.map((value, columnIndex) => {
    if (value === null || value === undefined || String(value).trim() === '') return '';
    const label = headerRows
      .map((_, rowIndex) => excelSummaryHeader(payload, rowIndex, columnIndex).trim())
      .filter((value, index, array) => value && array.indexOf(value) === index)
      .join(' ');
    return `<span class="candidate-excel-value"><b>${escapeHTML(label || `第 ${columnIndex + 1} 列`)}</b>${escapeHTML(value)}</span>`;
  }).filter(Boolean).join('');
  return values ? `<div class="candidate-excel-values">${values}</div>` : 'Excel 原始行没有可显示的内容。';
}

function syncRelatedCandidateSelectionControls() {
  const selectAll = document.querySelector('#candidate-select-all');
  const summary = document.querySelector('#candidate-selection-summary');
  const approveButton = document.querySelector('#bulk-approve-related');
  const checkboxes = [...document.querySelectorAll('#candidate-list [data-select-related-candidate]')];
  const selectedVisible = checkboxes.filter((checkbox) => checkbox.checked).length;
  if (selectAll) {
    selectAll.checked = checkboxes.length > 0 && selectedVisible === checkboxes.length;
    selectAll.indeterminate = selectedVisible > 0 && selectedVisible < checkboxes.length;
  }
  const selectedCount = state.selectedRelatedCandidateIds.size;
  if (summary) summary.textContent = `已选择 ${selectedCount} 条`;
  if (approveButton) approveButton.disabled = selectedCount === 0;
}

async function loadCandidates() {
  if (!hasCapability('related_review')) return;
  const data = await api('/api/related-info-candidates');
  const visibleIds = new Set(data.map((item) => item.id));
  state.selectedRelatedCandidateIds = new Set([...state.selectedRelatedCandidateIds].filter((candidateId) => visibleIds.has(candidateId)));
  document.querySelector('#candidate-count').textContent = data.length;
  document.querySelector('#candidate-empty').hidden = data.length > 0;
  document.querySelector('#candidate-bulk-toolbar').hidden = data.length === 0;
  const list = document.querySelector('#candidate-list');
  list.innerHTML = data.map((item) => {
    const location = [item.sheet, item.locator || (item.row ? `第 ${item.row} 行` : '')].filter(Boolean).join(' / ') || '原始文件';
    const isExcelCard = item.content_type === 'excel_card';
    const summary = isExcelCard ? excelRecordSummary(item.excel_payload) : escapeHTML(item.remarks);
    const approveLabel = isExcelCard ? '写入词条' : '写入备注';
    return `<article class="candidate"><div><h2>${escapeHTML(item.full_name)} <span class="status ${item.confidence >= 80 ? 'success' : 'pending'}">置信度 ${item.confidence}%</span></h2><div class="candidate-fields"><span><b>学号</b>${escapeHTML(item.student_no)}</span></div><div class="candidate-evidence${isExcelCard ? ' excel-record' : ''}">${summary}</div><p class="candidate-evidence">${escapeHTML(item.filename)}　${escapeHTML(location)}</p></div><div class="candidate-actions edit-only"><label class="candidate-select-control"><input type="checkbox" data-select-related-candidate="${item.id}"${state.selectedRelatedCandidateIds.has(item.id) ? ' checked' : ''}><span>选择</span></label><button class="button danger" data-reject-id="${item.id}">拒绝</button><button class="button primary" data-approve-id="${item.id}">${approveLabel}</button></div></article>`;
  }).join('');
  list.querySelectorAll('[data-select-related-candidate]').forEach((checkbox) => checkbox.addEventListener('change', () => {
    const candidateId = Number(checkbox.dataset.selectRelatedCandidate);
    if (checkbox.checked) state.selectedRelatedCandidateIds.add(candidateId); else state.selectedRelatedCandidateIds.delete(candidateId);
    syncRelatedCandidateSelectionControls();
  }));
  list.querySelectorAll('[data-approve-id]').forEach((button) => button.addEventListener('click', () => approveRelatedCandidate(Number(button.dataset.approveId))));
  list.querySelectorAll('[data-reject-id]').forEach((button) => button.addEventListener('click', () => rejectRelatedCandidate(Number(button.dataset.rejectId))));
  if (!hasCapability('related_review')) list.querySelectorAll('.edit-only').forEach((node) => { node.hidden = true; });
  syncRelatedCandidateSelectionControls();
  refreshIcons();
  await loadMatchReviews();
}

async function loadMatchReviews() {
  const section = document.querySelector('.match-review-section');
  const list = document.querySelector('#match-review-list');
  if (!section || !list) return;
  if (!hasCapability('related_review')) { section.hidden = true; return; }
  section.hidden = false;
  const records = await api('/api/import-match-reviews');
  list.innerHTML = records.length ? records.map((item) => {
    const identity = Object.entries(item.identity || {}).map(([key, value]) => `${fieldLabel(key)}：${value}`).join('；') || '未识别到身份信息';
    const suggestions = (item.suggestions || []).map((student) => `<button class="text-button" data-match-review="${item.id}" data-student-id="${student.id}">${escapeHTML(student.student_no)} · ${escapeHTML(student.full_name)}${student.current_class ? ` · ${escapeHTML(student.current_class)}` : ''}</button>`).join('');
    return `<article class="candidate match-review"><div><h2>${escapeHTML(identity)}</h2><p class="candidate-evidence">${escapeHTML(item.filename)}　${escapeHTML(item.reason || '需要人工确认')}</p><div class="candidate-evidence">${item.payload?.content_type === 'excel_card' ? excelRecordSummary(item.payload.excel_payload) : escapeHTML(item.payload?.remarks || '')}</div>${suggestions ? `<div class="match-suggestions">${suggestions}</div>` : ''}</div><div class="candidate-actions"><button class="button subtle" data-find-match="${item.id}">选择学生</button><button class="button danger" data-ignore-match="${item.id}">忽略</button></div></article>`;
  }).join('') : '<p class="source-empty">没有需要人工匹配的导入记录。</p>';
  list.querySelectorAll('[data-match-review]').forEach((button) => button.addEventListener('click', () => resolveMatchReview(Number(button.dataset.matchReview), Number(button.dataset.studentId))));
  list.querySelectorAll('[data-find-match]').forEach((button) => button.addEventListener('click', () => findAndResolveMatchReview(Number(button.dataset.findMatch))));
  list.querySelectorAll('[data-ignore-match]').forEach((button) => button.addEventListener('click', () => ignoreMatchReview(Number(button.dataset.ignoreMatch))));
}

async function resolveMatchReview(reviewId, studentId) {
  if (!confirm('确认关联该学生？系统会生成待审核项，尚不会直接写入备注。')) return;
  try { await api(`/api/import-match-reviews/${reviewId}/match`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({student_id: studentId})}); toast('已关联到学生，等待审核写入'); await Promise.all([loadCandidates(), loadDashboard()]); } catch (errorObject) { toast(errorObject.message, true); }
}

async function findAndResolveMatchReview(reviewId) {
  const keyword = window.prompt('输入要关联学生的学号、考生号或姓名：');
  if (!keyword?.trim()) return;
  try {
    const result = await api(`/api/students?keyword=${encodeURIComponent(keyword.trim())}&page_size=10`);
    if (!result.items?.length) { toast('没有找到学生，请检查输入。', true); return; }
    const choices = result.items.map((item) => `${item.id}: ${item.student_no} · ${item.full_name}`).join('\n');
    const selected = window.prompt(`找到以下学生，请输入 ID：\n${choices}`, String(result.items[0].id));
    const studentId = Number(selected);
    if (!studentId || !result.items.some((item) => item.id === studentId)) return;
    await resolveMatchReview(reviewId, studentId);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function ignoreMatchReview(reviewId) {
  if (!confirm('确认忽略这条无法匹配的导入记录？')) return;
  try { await api(`/api/import-match-reviews/${reviewId}/ignore`, {method:'POST'}); toast('该记录已忽略'); await loadMatchReviews(); } catch (errorObject) { toast(errorObject.message, true); }
}

function fieldLabel(field) {
  return ({student_no:'学号',candidate_no:'考生号',full_name:'姓名',gender:'性别',national_id:'身份证号',date_of_birth:'出生日期',student_origin:'生源地',ethnicity:'民族',political_status:'政治面貌',enrollment_date:'入学日期',graduation_year:'毕业年份',graduation_date:'毕业日期',urban_rural_origin:'城乡生源',pre_enrollment_archive_unit:'入学前档案所在单位',archive_transferred:'档案是否转入学校',pre_enrollment_police_station:'入学前户口所在地派出所',household_registration_transferred:'户口是否转入学校',education_level:'学历层次',program_duration:'学制',school:'所属学校',college:'所属学院',school_major:'学校专业',major_direction:'专业方向',current_class:'所在班级',training_mode:'培养方式',commissioned_unit:'委培单位',hardship_category:'困难生类别',normal_student_category:'师范生类别',mobile_phone:'手机号码',electronic_email:'电子邮箱',qq_number:'QQ号码',family_phone:'家庭电话',family_postcode:'家庭邮编',family_address:'家庭地址',poverty_county_52:'是否52个贫困县',poverty_county_province:'贫困县所在省',poverty_county_city:'贫困县所在市',poverty_county_district:'贫困县所在县',registered_poor:'是否建档立卡',study_mode:'学习形式',vocational_expansion_flag:'高职扩招考生标志',remarks:'备注'})[field] || field;
}

function capabilityLabel(capability) {
  return ({student_edit:'编辑档案',student_export:'导出数据',related_review:'审核相关信息',source_manage:'管理原始资料',quality_manage:'质量与运维',audit_view:'查看审计'})[capability] || capability;
}

function relatedInfoElements() {
  let section = document.querySelector('#student-related-info-section');
  if (!section) {
    const remarksLabel = document.querySelector('#student-form textarea[name="remarks"]').closest('label');
    section = document.createElement('section');
    section.id = 'student-related-info-section';
    section.className = 'remark-card-section span-2';
    section.hidden = true;
    section.innerHTML = '<div class="remark-card-list" id="student-related-info-cards"></div><div class="remark-card-preview" id="student-related-info-preview" hidden></div>';
    remarksLabel.insertAdjacentElement('afterend', section);
  }
  return {
    section,
    list: section.querySelector('#student-related-info-cards'),
    preview: section.querySelector('#student-related-info-preview'),
  };
}

function renderExcelRecord(payload) {
  const headerRows = Array.isArray(payload?.header_rows) ? payload.header_rows : [];
  const dataRow = Array.isArray(payload?.data_row) ? payload.data_row : [];
  const columnWidths = Array.isArray(payload?.column_widths) ? payload.column_widths : [];
  const merges = Array.isArray(payload?.merged_ranges) ? payload.merged_ranges : [];
  const rows = [...headerRows, dataRow];
  const mergeStarts = new Map();
  const covered = new Set();
  merges.forEach((merge) => {
    const startRow = Number(merge.start_row);
    const endRow = Number(merge.end_row);
    const startColumn = Number(merge.start_column);
    const endColumn = Number(merge.end_column);
    if (!startRow || !endRow || !startColumn || !endColumn) return;
    mergeStarts.set(`${startRow}:${startColumn}`, {rowspan: endRow - startRow + 1, colspan: endColumn - startColumn + 1});
    for (let row = startRow; row <= endRow; row += 1) {
      for (let column = startColumn; column <= endColumn; column += 1) {
        if (row !== startRow || column !== startColumn) covered.add(`${row}:${column}`);
      }
    }
  });
  const tableRows = rows.map((rowValues, rowIndex) => {
    const rowNumber = rowIndex + 1;
    const isHeader = rowIndex < headerRows.length;
    const cells = rowValues.map((value, columnIndex) => {
      const columnNumber = columnIndex + 1;
      const key = `${rowNumber}:${columnNumber}`;
      if (covered.has(key)) return '';
      const merge = mergeStarts.get(key);
      const width = Number(columnWidths[columnIndex]);
      const style = Number.isFinite(width) && width > 0 ? ` style="min-width:${Math.max(64, Math.min(260, Math.round(width * 7)))}px"` : '';
      const span = merge ? `${merge.colspan > 1 ? ` colspan="${merge.colspan}"` : ''}${merge.rowspan > 1 ? ` rowspan="${merge.rowspan}"` : ''}` : '';
      return `<${isHeader ? 'th' : 'td'}${span}${style}>${escapeHTML(value ?? '')}</${isHeader ? 'th' : 'td'}>`;
    }).join('');
    return `<tr>${cells}</tr>`;
  }).join('');
  return `<div class="remark-excel-table-wrap"><table class="remark-excel-table"><tbody>${tableRows}</tbody></table></div>`;
}

function showRelatedInfoPreview(card) {
  const {preview} = relatedInfoElements();
  preview.hidden = false;
  const studentId = state.currentStudent?.id;
  const sourceLink = card.source_available ? `<a href="/api/documents/${card.source_document_id}/download?student_id=${encodeURIComponent(studentId || '')}">原始文件</a>` : '<span class="subline">原始文件已删除</span>';
  preview.innerHTML = `<div class="remark-preview-head"><strong>${escapeHTML(card.title)}</strong>${sourceLink}</div>${renderExcelRecord(card.payload)}<div class="remark-preview-meta"><span>导入时间：${escapeHTML(dateTime(card.imported_at))}</span><span>导入人：${escapeHTML(card.imported_by)}</span></div>`;
}

function renderRelatedInfoCards(cards) {
  const {section, list, preview} = relatedInfoElements();
  section.hidden = cards.length === 0;
  preview.hidden = true;
  preview.replaceChildren();
  const mayEdit = ['super_admin', 'admin', 'teacher'].includes(state.user?.role);
  list.innerHTML = cards.map((card) => `<div class="remark-card-item"><button class="remark-card" type="button" data-related-card-id="${card.id}" title="查看 Excel 原始记录"><i data-lucide="file-spreadsheet"></i><span>${escapeHTML(card.title)}</span></button>${mayEdit ? `<button class="icon-button danger-icon remark-card-delete" type="button" data-delete-related-card-id="${card.id}" title="删除词条"><i data-lucide="x"></i></button>` : ''}</div>`).join('');
  list.querySelectorAll('[data-related-card-id]').forEach((node) => {
    const card = cards.find((item) => item.id === Number(node.dataset.relatedCardId));
    if (!card) return;
    node.addEventListener('pointerenter', () => showRelatedInfoPreview(card));
    node.addEventListener('focus', () => showRelatedInfoPreview(card));
    node.addEventListener('click', () => showRelatedInfoPreview(card));
  });
  list.querySelectorAll('[data-delete-related-card-id]').forEach((node) => {
    const card = cards.find((item) => item.id === Number(node.dataset.deleteRelatedCardId));
    if (!card) return;
    node.addEventListener('click', () => deleteRelatedInfoCard(card));
  });
  refreshIcons();
}

async function deleteRelatedInfoCard(card) {
  if (!state.currentStudent) return;
  if (!confirm(`确认删除“${card.title}”词条？学生备注、原始 Excel 文件和历史审计不会被删除。`)) return;
  try {
    await api(`/api/students/${state.currentStudent.id}/related-info-cards/${card.id}`, {method:'DELETE'});
    toast('学生相关信息词条已删除');
    await loadRelatedInfoCards(state.currentStudent.id);
  } catch (errorObject) {
    toast(errorObject.message, true);
  }
}

async function loadRelatedInfoCards(studentId) {
  const {section, list, preview} = relatedInfoElements();
  section.hidden = true;
  list.replaceChildren();
  preview.hidden = true;
  try {
    const cards = await api(`/api/students/${studentId}/related-info-cards`);
    if (state.currentStudent?.id !== studentId) return;
    renderRelatedInfoCards(cards);
  } catch (errorObject) {
    if (state.currentStudent?.id === studentId) toast(errorObject.message, true);
  }
}

function openStudentDialog(id = null) {
  const form = document.querySelector('#student-form');
  const error = document.querySelector('#student-form-error');
  error.textContent = '';
  state.currentStudent = id ? state.students.find((item) => item.id === id) : null;
  form.reset();
  const studentNo = form.elements.student_no;
  if (state.currentStudent) {
    document.querySelector('#student-dialog-title').textContent = '编辑学生';
    document.querySelector('#student-form-eyebrow').textContent = `版本 ${state.currentStudent.row_version}`;
    Object.entries(state.currentStudent).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value || ''; });
    studentNo.disabled = true;
  } else {
    document.querySelector('#student-dialog-title').textContent = '新建学生';
    document.querySelector('#student-form-eyebrow').textContent = '学生档案';
    studentNo.disabled = false;
  }
  document.querySelector('#student-dialog').showModal();
  if (state.currentStudent) {
    void loadRelatedInfoCards(state.currentStudent.id);
  } else {
    renderRelatedInfoCards([]);
  }
}

function cleanForm(form, excludes = []) {
  const value = Object.fromEntries(new FormData(form).entries());
  excludes.forEach((key) => delete value[key]);
  Object.keys(value).forEach((key) => { if (value[key] === '') value[key] = null; });
  return value;
}

async function saveStudent(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector('#student-form-error');
  error.textContent = '';
  let payload = cleanForm(form, state.currentStudent ? ['student_no'] : []);
  if (state.currentStudent) payload.row_version = state.currentStudent.row_version;
  try {
    const path = state.currentStudent ? `/api/students/${state.currentStudent.id}` : '/api/students';
    await api(path, {method: state.currentStudent ? 'PATCH' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    document.querySelector('#student-dialog').close();
    toast('学生档案已保存');
    await Promise.all([loadStudents(), loadDashboard()]);
  } catch (errorObject) { error.textContent = errorObject.message; }
}

async function deleteStudent(id) {
  const student = state.students.find((item) => item.id === id);
  if (!student) return;
  if (!confirm(`第一次确认：确定要删除 ${student.full_name} 的全部学生档案信息吗？此操作不可恢复。`)) return;
  const studentNo = window.prompt(`第二次确认：请输入学号 ${student.student_no}。`);
  if (studentNo !== student.student_no) {
    toast('学号不匹配，已取消删除。', true);
    return;
  }
  const phrase = window.prompt('第三次确认：请输入“永久删除”以删除该学生档案及字段来源。');
  if (phrase !== '永久删除') {
    toast('确认口令不正确，已取消删除。', true);
    return;
  }
  try {
    await api(`/api/students/${student.id}`, {method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({student_no: student.student_no, confirmation_phrase: phrase})});
    state.selectedStudentIds.delete(student.id);
    toast('学生档案已永久删除');
    await Promise.all([loadStudents(), loadDashboard(), loadCandidates()]);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function openVersionDialog(studentId) {
  try {
    const versions = await api(`/api/students/${studentId}/versions`);
    const student = state.students.find((item) => item.id === studentId);
    document.querySelector('#version-dialog-title').textContent = `${student?.full_name || '学生'}的版本记录`;
    const list = document.querySelector('#version-list');
    list.innerHTML = versions.length ? versions.map((version) => {
      const fields = (version.changed_fields || []).map(fieldLabel).join('、') || '完整快照';
      const snapshot = version.snapshot || {};
      const summary = [snapshot.student_no, snapshot.full_name, snapshot.school_major, snapshot.current_class].filter(Boolean).join(' · ');
      const mayRestore = ['super_admin', 'admin'].includes(state.user?.role);
      return `<article class="source-row"><strong>版本 ${escapeHTML(version.version_no)} · ${escapeHTML(fields)}</strong><div class="source-meta"><span>${escapeHTML(summary || '-')}</span><span>${escapeHTML(version.changed_by)}</span><time>${dateTime(version.created_at)}</time>${mayRestore ? `<button class="text-button" data-restore-version="${version.id}" data-student-id="${studentId}">恢复此版本</button>` : ''}</div></article>`;
    }).join('') : '<p class="source-empty">暂无版本记录。</p>';
    list.querySelectorAll('[data-restore-version]').forEach((button) => button.addEventListener('click', () => restoreStudentVersion(Number(button.dataset.studentId), Number(button.dataset.restoreVersion))));
    document.querySelector('#version-dialog').showModal();
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function restoreStudentVersion(studentId, versionId) {
  if (!confirm('确认将学生档案恢复到这个历史版本？当前状态会自动保留为一个新版本。')) return;
  try {
    await api(`/api/students/${studentId}/versions/${versionId}/restore`, {method:'POST'});
    toast('学生档案已恢复到所选版本');
    await loadStudents();
    await openVersionDialog(studentId);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function openSourceDialog(studentId) {
  const student = state.students.find((item) => item.id === studentId);
  const records = await api(`/api/students/${studentId}/provenance`);
  document.querySelector('#source-dialog-title').textContent = `${student.full_name}的数据来源`;
  document.querySelector('#source-list').innerHTML = records.length ? records.map((item) => {
    const location = [item.sheet, item.locator || (item.row ? `第 ${item.row} 行` : '')].filter(Boolean).join(' / ') || '平台编辑';
    return `<article class="source-row"><strong>${escapeHTML(fieldLabel(item.field_name))}: ${escapeHTML(item.raw_value || '-')}</strong><div class="source-meta"><span class="source-file">${escapeHTML(item.file)}</span>${item.document_id && item.document_available ? `<a href="/api/documents/${item.document_id}/download?student_id=${encodeURIComponent(studentId)}">原始文件</a>` : '<span class="subline">原始文件已删除</span>'}<span class="source-location">${escapeHTML(location)}</span><time class="source-time">${dateTime(item.recorded_at)}</time></div></article>`;
  }).join('') : '<p class="source-empty">没有记录到字段来源。</p>';
  document.querySelector('#source-dialog').showModal();
}

async function openTimelineDialog(studentId) {
  try {
    const student = state.students.find((item) => item.id === studentId);
    const events = await api(`/api/students/${studentId}/timeline`);
    document.querySelector('#timeline-dialog-title').textContent = `${student?.full_name || '学生'}的时间线`;
    document.querySelector('#timeline-list').innerHTML = events.length ? events.map((item) => `<article class="source-row timeline-${escapeHTML(item.type)}"><strong>${escapeHTML(item.title)}</strong><div class="source-meta"><span>${escapeHTML((item.detail || '').split('、').map(fieldLabel).join('、') || '-')}</span><span>${escapeHTML(item.actor || '系统')}</span><time>${dateTime(item.at)}</time></div></article>`).join('') : '<p class="source-empty">尚无可展示的学生档案事件。</p>';
    document.querySelector('#timeline-dialog').showModal();
  } catch (errorObject) { toast(errorObject.message, true); }
}

const importableStudentFields = ['student_no', 'candidate_no', 'full_name', 'gender', 'national_id', 'date_of_birth', 'student_origin', 'ethnicity', 'political_status', 'enrollment_date', 'graduation_year', 'graduation_date', 'urban_rural_origin', 'pre_enrollment_archive_unit', 'archive_transferred', 'pre_enrollment_police_station', 'household_registration_transferred', 'education_level', 'program_duration', 'school', 'college', 'school_major', 'major_direction', 'current_class', 'training_mode', 'commissioned_unit', 'hardship_category', 'normal_student_category', 'mobile_phone', 'electronic_email', 'qq_number', 'family_phone', 'family_postcode', 'family_address', 'poverty_county_52', 'poverty_county_province', 'poverty_county_city', 'poverty_county_district', 'registered_poor', 'study_mode', 'vocational_expansion_flag', 'remarks'];

function currentExcelMapping() {
  return Object.fromEntries([...document.querySelectorAll('#excel-import-preview [data-import-column]')].map((select) => [select.dataset.importColumn, select.value || null]));
}

function renderExcelPreview(data) {
  state.excelPreview = data;
  const panel = document.querySelector('#excel-import-preview');
  const columns = data.columns || [];
  const options = (selected) => [`<option value="">不导入</option>`, ...importableStudentFields.map((field) => `<option value="${field}"${selected === field ? ' selected' : ''}>${escapeHTML(fieldLabel(field))}</option>`)].join('');
  const mapping = columns.map((column) => `<label class="mapping-row"><span><strong>${escapeHTML(column.column)} · ${escapeHTML(column.header)}</strong><span>原始列</span></span><select data-import-column="${escapeHTML(column.column)}">${options(column.field)}</select></label>`).join('');
  const previewColumns = columns.slice(0, 16);
  const samples = (data.samples || []).map((sample) => `<tr><td>${sample.row}</td>${previewColumns.map((column) => `<td>${escapeHTML(sample.values?.[column.column] || '')}</td>`).join('')}</tr>`).join('') || '<tr><td colspan="99">没有可预览的数据行</td></tr>';
  const conflicts = (data.conflicts || []).map((conflict) => `<article class="conflict-row"><strong>第 ${conflict.row} 行 · ${escapeHTML(conflict.student_no)} · ${escapeHTML(conflict.full_name || '')}</strong>${conflict.changes.map((change) => `<div class="conflict-change">${escapeHTML(fieldLabel(change.field))}：<s>${escapeHTML(change.before || '空')}</s> → ${escapeHTML(change.after || '空')}</div>`).join('')}</article>`).join('') || '<p class="source-empty">未发现需要覆盖的现有字段。</p>';
  const issues = (data.issues || []).map((item) => `<article class="conflict-row"><strong>第 ${item.row} 行</strong><div class="conflict-change">${escapeHTML(item.message)}</div></article>`).join('') || '<p class="source-empty">未发现格式问题或重复学号。</p>';
  panel.innerHTML = `<div class="import-preview-heading"><div><h3>导入预检</h3><p>${escapeHTML(data.filename || '')} · ${escapeHTML(data.sheet_name || '')}。确认映射与冲突后才能写入数据库。</p><p>更新策略：${data.update_policy === 'only_blank' ? '仅补空值' : '覆盖已有值'}；必填字段：${escapeHTML((data.required_fields || []).map(fieldLabel).join('、') || '学号、姓名')}</p></div><span class="status ${data.conflict_rows || data.invalid_rows || data.duplicate_rows ? 'pending' : 'success'}">${data.conflict_rows || data.invalid_rows || data.duplicate_rows ? '需核对' : '可导入'}</span></div><div class="import-preview-stats"><div class="import-preview-stat"><span>有效行</span><strong>${data.valid_rows}</strong></div><div class="import-preview-stat"><span>新增</span><strong>${data.new_rows}</strong></div><div class="import-preview-stat"><span>更新冲突</span><strong>${data.conflict_rows}</strong></div><div class="import-preview-stat"><span>错误 / 重复</span><strong>${data.invalid_rows + data.duplicate_rows}</strong></div></div><div class="import-preview-grid"><section><h3>字段映射</h3><div class="mapping-list">${mapping}</div></section><section><h3>样本行</h3><div class="import-preview-table"><table><thead><tr><th>行</th>${previewColumns.map((column) => `<th>${escapeHTML(column.header)}</th>`).join('')}</tr></thead><tbody>${samples}</tbody></table></div></section></div><div class="import-preview-grid"><section><h3>字段冲突</h3><div class="conflict-list">${conflicts}</div></section><section><h3>问题与重复</h3><div class="conflict-list">${issues}</div></section></div><div class="import-preview-actions"><button class="button subtle" type="button" id="refresh-excel-preview"><i data-lucide="refresh-cw"></i>按当前映射重新预检</button><button class="button primary" type="button" id="commit-excel-import"><i data-lucide="database-zap"></i>确认导入</button></div>`;
  panel.hidden = false;
  document.querySelector('#refresh-excel-preview').addEventListener('click', () => previewExcelImport());
  document.querySelector('#commit-excel-import').addEventListener('click', commitExcelImport);
  refreshIcons();
}

async function previewExcelImport(event = null) {
  event?.preventDefault();
  const form = document.querySelector('#excel-import-form');
  const output = document.querySelector('#excel-import-result');
  const button = form.querySelector('button[type="submit"]');
  const file = form.elements.file.files[0];
  if (!file) {
    output.textContent = '请先选择 Excel 文件。';
    output.hidden = false;
    return;
  }
  const originalButton = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '<i data-lucide="loader-circle"></i> 正在预检';
  output.textContent = '正在读取表头、样本行、重复学号和已有字段差异。';
  output.hidden = false;
  refreshIcons();
  try {
    const formData = new FormData(form);
    const selectedTemplate = state.importTemplates.find((template) => String(template.id) === String(form.elements.template_id.value));
    const mapping = state.excelPreview ? currentExcelMapping() : selectedTemplate?.mapping || null;
    if (mapping) formData.set('mapping_json', JSON.stringify(mapping));
    const typedRequired = form.elements.required_fields.value.split(/[,，]/).map(normalizeTemplateField).filter(Boolean);
    const requiredFields = [...new Set([...(selectedTemplate?.required_fields || []), ...typedRequired])];
    formData.set('required_fields_json', JSON.stringify(requiredFields));
    if (!state.excelPreview && selectedTemplate) {
      formData.set('mode', selectedTemplate.default_mode);
      formData.set('update_policy', selectedTemplate.update_policy);
    }
    const data = await api('/api/imports/excel/preview', {method:'POST', body:formData});
    renderExcelPreview(data);
    output.textContent = `预检完成：共 ${data.total_rows} 行，有效 ${data.valid_rows} 行，发现 ${data.conflict_rows} 行字段冲突。`;
    toast('Excel 预检完成，请确认后导入');
  } catch (errorObject) {
    output.textContent = errorObject.message;
    toast(errorObject.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = originalButton;
    refreshIcons();
  }
}

async function commitExcelImport() {
  if (!state.excelPreview) return;
  if (!confirm('确认按当前预检结果写入学生主档案？字段冲突将按导入方式处理。')) return;
  const button = document.querySelector('#commit-excel-import');
  const output = document.querySelector('#excel-import-result');
  const form = document.querySelector('#excel-import-form');
  const preview = state.excelPreview;
  const mapping = currentExcelMapping();
  button.disabled = true;
  try {
    let data = await api('/api/imports/excel/commit', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({preview_id: preview.preview_id, mode: preview.mode, mapping, required_fields: preview.required_fields || [], update_policy: preview.update_policy || 'overwrite', background_task: true})});
    document.querySelector('#excel-import-preview').hidden = true;
    state.excelPreview = null;
    form.reset();
    if (data.task?.id) {
      output.textContent = '导入已进入后台队列，正在处理 Excel 数据。';
      data = (await waitForTask(data.task.id)).result;
    }
    output.textContent = `导入完成：总计 ${data.total_rows}，新增 ${data.created_rows}，更新 ${data.updated_rows}，跳过 ${data.skipped_rows}，错误 ${data.error_rows}`;
    toast('学生数据已按预检结果导入');
    await Promise.all([loadImports(), loadDashboard(), loadStudents()]);
  } catch (errorObject) {
    output.textContent = errorObject.message;
    toast(errorObject.message, true);
  } finally {
    button.disabled = false;
  }
}

async function submitImport(event, type) {
  event.preventDefault();
  if (type === 'excel') return previewExcelImport();
  const form = event.currentTarget;
  const isStudentImport = false;
  const output = document.querySelector('#related-import-result');
  const submitButton = form.querySelector('button[type="submit"]');
  const originalButton = submitButton.innerHTML;
  const relatedFile = form.elements.file.files[0];
  const isRelatedExcel = !isStudentImport && relatedFile?.name.toLowerCase().endsWith('.xlsx');
  submitButton.disabled = true;
  if (!isStudentImport) {
    submitButton.innerHTML = isRelatedExcel ? '<i data-lucide="loader-circle"></i> 读取 Excel 原始行中' : '<i data-lucide="loader-circle"></i> 本地 AI 分析中';
    output.textContent = isRelatedExcel ? '正在读取第一个非隐藏工作表并生成待审核词条，请勿关闭页面。' : '正在分析 Word 文件并生成待审核备注，请勿关闭页面。';
    output.hidden = false;
    refreshIcons();
  } else {
    output.hidden = true;
  }
  try {
    const formData = new FormData(form);
    formData.set('background', 'true');
    let data = await api(`/api/imports/${type}`, {method:'POST', body:formData});
    if (data.task?.id) {
      output.textContent = '任务已进入后台队列，正在处理文件。';
      data = (await waitForTask(data.task.id)).result;
    }
    output.textContent = isStudentImport
      ? `处理完成：总计 ${data.total_rows}，新增 ${data.created_rows}，更新 ${data.updated_rows}，跳过 ${data.skipped_rows}，错误 ${data.error_rows}`
      : isRelatedExcel
        ? `Excel 读取完成：记录 ${data.total_rows}，待审核 ${data.created_rows}，跳过 ${data.skipped_rows}，错误 ${data.error_rows}`
        : `Word AI 分析完成：分析片段 ${data.total_rows}，待审核 ${data.created_rows}，跳过 ${data.skipped_rows}，错误 ${data.error_rows}`;
    output.hidden = false;
    form.reset();
    toast(isStudentImport ? '学生数据导入完成' : '学生相关信息已提交审核');
    await Promise.all([loadImports(), loadDashboard(), loadCandidates()]);
  } catch (errorObject) {
    output.textContent = errorObject.message;
    output.hidden = false;
    toast(errorObject.message, true);
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = originalButton;
    refreshIcons();
  }
}

async function approveRelatedCandidate(id) {
  if (!confirm('确认将该信息写入学生备注？')) return;
  try {
    await api(`/api/related-info-candidates/${id}/approve`, {method:'POST'});
    state.selectedRelatedCandidateIds.delete(id);
    toast('学生备注已写入');
    await Promise.all([loadCandidates(), loadStudents(), loadDashboard()]);
  } catch (errorObject) { toast(errorObject.message, true); }
}

async function bulkApproveRelatedCandidates() {
  const candidateIds = [...state.selectedRelatedCandidateIds];
  if (!candidateIds.length) { toast('请先选择待审核的学生相关信息。', true); return; }
  if (!confirm(`确认将选中的 ${candidateIds.length} 条学生相关信息写入学生备注或词条？所有记录都会留下审核审计。`)) return;
  const button = document.querySelector('#bulk-approve-related');
  button.disabled = true;
  try {
    const result = await api('/api/related-info-candidates/bulk-approve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({candidate_ids: candidateIds})});
    state.selectedRelatedCandidateIds.clear();
    toast(result.message || `已确认 ${result.approved_count} 条学生相关信息`);
    await Promise.all([loadCandidates(), loadStudents(), loadDashboard()]);
  } catch (errorObject) {
    toast(errorObject.message, true);
  } finally {
    syncRelatedCandidateSelectionControls();
  }
}

async function rejectRelatedCandidate(id) {
  if (!confirm('拒绝此学生相关信息审核项？')) return;
  try { await api(`/api/related-info-candidates/${id}/reject`, {method:'POST'}); toast('审核项已拒绝'); await Promise.all([loadCandidates(), loadDashboard()]); } catch (errorObject) { toast(errorObject.message, true); }
}

function exportPreviewFilters(options = {}) {
  return Object.fromEntries(['keyword', 'current_class', 'school_major', 'college', 'school'].map((key) => [key, options[key]]).filter(([, value]) => value !== null && value !== undefined && value !== ''));
}

async function openExportPreview(options = {}, template = null) {
  const selectedStudentIds = Array.isArray(options.student_ids) && options.student_ids.length ? options.student_ids : null;
  const payload = {filters: exportPreviewFilters(options), student_ids: selectedStudentIds || undefined, fields: template?.fields || []};
  const dialog = document.querySelector('#export-preview-dialog');
  const content = document.querySelector('#export-preview-content');
  content.innerHTML = '<p class="source-empty">正在计算导出范围...</p>';
  dialog.showModal();
  try {
    const result = await api('/api/exports/preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    state.pendingExport = template ? {type:'template', id:template.id} : {type:'direct', options};
    const filterSummary = Object.entries(result.filters || {}).map(([key, value]) => `${fieldLabel(key)}：${value}`).join('；') || (selectedStudentIds ? '已选择学生' : '全部可访问学生');
    const samples = result.samples || [];
    content.innerHTML = `<div class="export-preview-summary"><strong>将导出 ${result.total} 条学生记录</strong><span>${escapeHTML(filterSummary)}</span><span>字段：${escapeHTML((result.fields || []).map((item) => item.label).join('、'))}</span></div><div class="export-preview-samples"><h3>样本记录</h3>${samples.length ? `<table><thead><tr><th>学号</th><th>姓名</th><th>所属学校</th><th>所属学院</th><th>学校专业</th><th>所在班级</th></tr></thead><tbody>${samples.map((student) => `<tr><td>${escapeHTML(student.student_no)}</td><td>${escapeHTML(student.full_name)}</td><td>${escapeHTML(student.school || '-')}</td><td>${escapeHTML(student.college || '-')}</td><td>${escapeHTML(student.school_major || '-')}</td><td>${escapeHTML(student.current_class || '-')}</td></tr>`).join('')}</tbody></table>` : '<p class="source-empty">当前条件没有匹配的学生。</p>'}</div>`;
    document.querySelector('#confirm-export-preview').disabled = result.total === 0;
  } catch (errorObject) {
    state.pendingExport = null;
    content.innerHTML = `<p class="source-empty">${escapeHTML(errorObject.message)}</p>`;
    document.querySelector('#confirm-export-preview').disabled = true;
  }
}

async function createExport(filters = {}) {
  const params = new URLSearchParams();
  const selectedStudentIds = Array.isArray(filters.student_ids) && filters.student_ids.length ? filters.student_ids : null;
  Object.entries(filters).forEach(([key, value]) => {
    if (key !== 'student_ids' && value !== null && value !== undefined && value !== '') params.set(key, value);
  });
  const options = selectedStudentIds
    ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({student_ids:selectedStudentIds})}
    : {method:'POST'};
  const data = await api(`/api/exports?${params.toString()}`, options);
  if (data.download_url) {
    window.location.assign(data.download_url);
    return;
  }
  const taskId = data.task?.id;
  if (!taskId) throw new Error('导出任务创建失败');
  toast('导出任务已加入后台队列');
  const task = await waitForTask(taskId);
  if (task.result?.download_url) window.location.assign(task.result.download_url);
}

async function executePendingExport() {
  const pending = state.pendingExport;
  if (!pending) return;
  const button = document.querySelector('#confirm-export-preview');
  button.disabled = true;
  try {
    if (pending.type === 'template') await exportTemplate(pending.id);
    else await createExport(pending.options);
    document.querySelector('#export-preview-dialog').close();
    state.pendingExport = null;
  } catch (errorObject) { toast(errorObject.message, true); }
  finally { button.disabled = false; }
}

async function previewReportExport() {
  const form = document.querySelector('#report-export-form');
  const data = new FormData(form);
  const templateId = Number(data.get('template_id') || 0);
  if (templateId) {
    const template = state.exportTemplates.find((item) => item.id === templateId);
    if (!template) throw new Error('导出模板不存在，请刷新后重试。');
    await openExportPreview({...template.filters}, template);
    return;
  }
  await openExportPreview({
    keyword: data.get('keyword'),
    current_class: data.get('current_class'),
    include_provenance: data.get('include_provenance') ? 'true' : 'false',
    mask_sensitive: data.get('mask_sensitive') ? 'true' : 'false',
  });
}

async function waitForTask(taskId, timeoutSeconds = 180) {
  for (let attempt = 0; attempt < timeoutSeconds; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    const task = await api(`/api/tasks/${encodeURIComponent(taskId)}`);
    if (task.status === 'completed') return task;
    if (task.status === 'failed') throw new Error(task.error_message || '后台任务失败');
  }
  throw new Error('任务仍在后台执行，可在“质量与运维”的后台任务中查看结果。');
}

function renderAiSources(sources = []) {
  if (!sources.length) return '';
  return `<div class="chat-sources">${sources.map((source) => `<span class="chat-source"><b>来源：${escapeHTML(source.title || '系统')}</b> ${escapeHTML(source.detail || '')}</span>`).join('')}</div>`;
}

function appendAiSources(node, sources = []) {
  if (!sources.length) return;
  const wrapper = document.createElement('div');
  wrapper.innerHTML = renderAiSources(sources);
  if (wrapper.firstElementChild) node.append(wrapper.firstElementChild);
}

async function confirmAiAction(actionId, button) {
  button.disabled = true;
  try {
    const data = await api(`/api/ai/actions/${encodeURIComponent(actionId)}/confirm`, {method:'POST'});
    const node = appendChat('result', escapeHTML(data.reply));
    appendAiSources(node, data.sources || []);
    if (data.download_url) {
      const link = document.createElement('a');
      link.href = data.download_url;
      link.textContent = '下载 XLSX';
      node.append(document.createElement('br'), link);
    }
  } catch (errorObject) {
    button.disabled = false;
    toast(errorObject.message, true);
  }
}

function appendChat(kind, html) {
  const log = document.querySelector('#chat-log');
  const node = document.createElement('div');
  node.className = `chat-message ${kind}`;
  node.innerHTML = html;
  log.append(node);
  log.scrollTop = log.scrollHeight;
  return node;
}

function aiConversationStorageKey() {
  const sessionId = cookieValue('ai_session_id') || 'legacy';
  return state.user ? `student-management-ai-conversation-${state.user.id}-${sessionId}` : 'student-management-ai-conversation';
}

function resetAiConversationUI() {
  const log = document.querySelector('#chat-log');
  log.replaceChildren();
  appendChat('system', '请查询学生信息或生成数据导出。');
  loadAiSuggestions();
}

function hideAiSuggestions() {
  state.aiSuggestionRequest += 1;
  const panel = document.querySelector('#assistant-suggestions');
  panel.replaceChildren();
  panel.hidden = true;
}

async function loadAiSuggestions() {
  const requestId = ++state.aiSuggestionRequest;
  const panel = document.querySelector('#assistant-suggestions');
  panel.replaceChildren();
  panel.hidden = true;
  try {
    const data = await api('/api/ai/suggestions');
    if (requestId !== state.aiSuggestionRequest || document.querySelector('#chat-log .chat-message.user, #chat-log .chat-message.result')) return;
    const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
    if (!suggestions.length) return;
    const heading = document.createElement('p');
    heading.className = 'assistant-suggestions-title';
    heading.textContent = '猜你喜欢';
    const bubbles = document.createElement('div');
    bubbles.className = 'assistant-suggestion-bubbles';
    suggestions.forEach((suggestion) => {
      const question = String(suggestion?.question || '').trim();
      if (!question) return;
      const button = document.createElement('button');
      button.className = 'assistant-suggestion';
      button.type = 'button';
      button.textContent = String(suggestion.label || question);
      button.addEventListener('click', () => submitAssistantQuestion(question));
      bubbles.append(button);
    });
    if (!bubbles.childElementCount) return;
    panel.append(heading, bubbles);
    panel.hidden = false;
  } catch (_) {
    // Suggestions are optional. The assistant remains available if this lookup fails.
  }
}

async function loadAiConversation() {
  state.aiConversationId = sessionStorage.getItem(aiConversationStorageKey());
  if (!state.aiConversationId) {
    resetAiConversationUI();
    return;
  }
  try {
    const data = await api(`/api/ai/conversations/${encodeURIComponent(state.aiConversationId)}`);
    const log = document.querySelector('#chat-log');
    log.replaceChildren();
    if (!data.messages.length) {
      resetAiConversationUI();
      return;
    }
    hideAiSuggestions();
    data.messages.forEach((message) => {
      const node = appendChat(message.role === 'user' ? 'user' : 'result', escapeHTML(message.content));
      if (message.role !== 'user') appendAiSources(node, message.sources || []);
    });
  } catch (_) {
    sessionStorage.removeItem(aiConversationStorageKey());
    state.aiConversationId = null;
    resetAiConversationUI();
  }
}

async function clearAiConversation() {
  if (!state.aiConversationId) {
    resetAiConversationUI();
    return;
  }
  if (!confirm('清空当前 AI 对话及上下文？')) return;
  try {
    await api(`/api/ai/conversations/${encodeURIComponent(state.aiConversationId)}`, {method: 'DELETE'});
    sessionStorage.removeItem(aiConversationStorageKey());
    state.aiConversationId = null;
    resetAiConversationUI();
  } catch (errorObject) {
    toast(errorObject.message, true);
  }
}

function scrollChatToEnd() {
  const log = document.querySelector('#chat-log');
  log.scrollTop = log.scrollHeight;
}

async function streamAssistantResponse(question, node) {
  const response = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken()},
    body: JSON.stringify({question, conversation_id: state.aiConversationId}),
  });
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) window.location.assign('/login');
    throw new Error(payload.detail || 'AI 响应失败，请稍后重试。');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  let typed = '';
  let completed = null;
  node.classList.add('streaming');
  while (true) {
    const {done, value} = await reader.read();
    pending += decoder.decode(value || new Uint8Array(), {stream: !done}).replace(/\r\n/g, '\n');
    const events = pending.split('\n\n');
    pending = events.pop();
    for (const eventBlock of events) {
      const eventName = eventBlock.match(/^event:\s*(.+)$/m)?.[1];
      const dataText = eventBlock.match(/^data:\s*(.+)$/m)?.[1];
      if (!eventName || !dataText) continue;
      const data = JSON.parse(dataText);
      if (eventName === 'delta') {
        typed += data.text;
        node.textContent = typed;
        scrollChatToEnd();
      } else if (eventName === 'done') {
        completed = data;
      }
    }
    if (done) break;
  }
  node.classList.remove('streaming');
  if (completed?.conversation_id) {
    state.aiConversationId = completed.conversation_id;
    sessionStorage.setItem(aiConversationStorageKey(), state.aiConversationId);
  }
  if (completed?.download_url) {
    const link = document.createElement('a');
    link.href = completed.download_url;
    link.textContent = '下载 XLSX';
    node.append(document.createElement('br'), link);
  }
  appendAiSources(node, completed?.sources || []);
  if (completed?.diff_preview?.length) {
    const detail = document.createElement('details');
    detail.className = 'chat-diff-preview';
    detail.innerHTML = `<summary>查看前 ${completed.diff_preview.length} 条修改差异</summary>${completed.diff_preview.map((row) => `<p><b>${escapeHTML(row.student_no)} ${escapeHTML(row.full_name)}</b><br>${(row.changes || []).map((change) => `${escapeHTML(change.label)}：${escapeHTML(change.before || '空')} → ${escapeHTML(change.after || '空')}`).join('；') || '无变化'}</p>`).join('')}`;
    node.append(detail);
  }
  if (completed?.confirmation?.action_id) {
    const confirmation = document.createElement('div');
    confirmation.className = 'chat-confirmation';
    const button = document.createElement('button');
    button.className = 'button primary';
    button.type = 'button';
    button.textContent = completed.confirmation.label || '确认执行';
    button.addEventListener('click', () => confirmAiAction(completed.confirmation.action_id, button));
    confirmation.append(button);
    node.append(confirmation);
  }
  scrollChatToEnd();
  return completed;
}

async function submitAssistantQuestion(question) {
  question = String(question || '').trim();
  if (!question) return;
  hideAiSuggestions();
  document.querySelector('#ai-question').value = '';
  appendChat('user', escapeHTML(question));
  const resultNode = appendChat('result', '');
  try {
    const data = await streamAssistantResponse(question, resultNode);
    if (data.intent === 'search') { await loadStudents(); }
  } catch (errorObject) { resultNode.remove(); appendChat('system', escapeHTML(errorObject.message)); }
}

async function askAssistant(event) {
  event.preventDefault();
  await submitAssistantQuestion(document.querySelector('#ai-question').value);
}

async function logout() {
  if (state.idleLogoutTimer) window.clearTimeout(state.idleLogoutTimer);
  state.idleLogoutTimer = null;
  sessionStorage.removeItem(aiConversationStorageKey());
  state.aiConversationId = null;
  try { await api('/api/auth/logout', {method:'POST'}); } finally { window.location.assign('/login'); }
}

function resetIdleLogoutTimer() {
  if (!state.user || state.idleLogoutStarted) return;
  state.lastActivityAt = Date.now();
  if (state.idleLogoutTimer) window.clearTimeout(state.idleLogoutTimer);
  state.idleLogoutTimer = window.setTimeout(() => {
    state.idleLogoutTimer = null;
    if (Date.now() - state.lastActivityAt >= IDLE_LOGOUT_TIMEOUT_MS) {
      state.idleLogoutStarted = true;
      logout();
      return;
    }
    resetIdleLogoutTimer();
  }, IDLE_LOGOUT_TIMEOUT_MS);
}

function checkIdleLogout() {
  if (!state.user || state.idleLogoutStarted || !state.lastActivityAt) return;
  if (Date.now() - state.lastActivityAt >= IDLE_LOGOUT_TIMEOUT_MS) {
    state.idleLogoutStarted = true;
    logout();
    return;
  }
  resetIdleLogoutTimer();
}

function startIdleLogoutTimer() {
  state.idleLogoutStarted = false;
  resetIdleLogoutTimer();
  ['keydown', 'pointerdown', 'touchstart', 'wheel', 'scroll'].forEach((eventName) => {
    document.addEventListener(eventName, resetIdleLogoutTimer, {passive: true});
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) checkIdleLogout();
  });
}

async function refreshAll() {
  try { await loadStudentFilterOptions(); await Promise.all([loadDashboard(), loadStudents(), loadImports(), loadCandidates()]); toast('数据已刷新'); } catch (errorObject) { toast(errorObject.message, true); }
}

function bindEvents() {
  syncAssistantLayout();
  document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
  document.querySelectorAll('[data-go-view]').forEach((button) => {
    button.addEventListener('click', () => setView(button.dataset.goView));
    if (button.getAttribute('role') === 'button') button.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setView(button.dataset.goView); } });
  });
  document.querySelectorAll('[data-focus-ai]').forEach((button) => button.addEventListener('click', () => {
    setAssistantOpen(true);
  }));
  document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('.app-shell').classList.toggle('menu-open'));
  document.querySelector('#mobile-nav-backdrop').addEventListener('click', () => document.querySelector('.app-shell').classList.remove('menu-open'));
  document.querySelector('#assistant-launch').addEventListener('click', () => setAssistantOpen(true));
  document.querySelector('#assistant-collapse').addEventListener('click', () => setAssistantOpen(false));
  document.querySelector('#mobile-assistant-close').addEventListener('click', () => setAssistantOpen(false));
  window.addEventListener('resize', syncAssistantLayout);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && document.querySelector('.app-shell').classList.contains('assistant-open')) setAssistantOpen(false);
    if (event.key === 'Escape') hideImportReportPreview();
  });
  const importReportPopover = document.querySelector('#import-report-popover');
  importReportPopover.addEventListener('pointerenter', () => clearTimeout(state.importReportHideTimer));
  importReportPopover.addEventListener('pointerleave', hideImportReportPreview);
  importReportPopover.addEventListener('click', (event) => {
    if (event.target.closest('[data-close-import-report]')) hideImportReportPreview();
    if (event.target.closest('[data-open-import-match-review]')) { hideImportReportPreview(); setView('candidates'); }
    const retryButton = event.target.closest('[data-open-import-retry]');
    if (retryButton) { hideImportReportPreview(); openImportRetryDialog(Number(retryButton.dataset.openImportRetry)); }
  });
  window.addEventListener('scroll', handleImportReportScroll, true);
  window.addEventListener('blur', hideImportReportPreview);
  document.addEventListener('visibilitychange', () => { if (document.hidden) hideImportReportPreview(); });
  document.querySelector('#refresh-button').addEventListener('click', refreshAll);
  document.querySelector('#account-security-button').addEventListener('click', () => openAccountSecurityDialog(false));
  document.querySelector('#logout-button').addEventListener('click', logout);
  document.querySelector('#student-search').addEventListener('input', (() => { let timer; return () => { clearStudentSelection(); state.studentPage = 1; clearTimeout(timer); timer = setTimeout(loadStudents, 260); }; })());
  document.querySelector('#student-filters').addEventListener('change', handleStudentFilterChange);
  document.querySelector('#student-filters').addEventListener('reset', () => { clearStudentSelection(); window.setTimeout(() => { state.studentPage = 1; loadStudentFilterOptions().then(loadStudents).catch((errorObject) => toast(errorObject.message, true)); }, 0); });
  document.querySelector('#apply-saved-student-filter').addEventListener('click', () => applySavedStudentFilter().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#save-student-filter').addEventListener('click', () => saveCurrentStudentFilter());
  document.querySelector('#delete-saved-student-filter').addEventListener('click', () => deleteSavedStudentFilter());
  document.querySelector('#students-previous-page').addEventListener('click', () => { if (state.studentPage > 1) { state.studentPage -= 1; loadStudents(); } });
  document.querySelector('#students-next-page').addEventListener('click', () => { if (state.studentPage < state.studentTotalPages) { state.studentPage += 1; loadStudents(); } });
  document.querySelector('#new-student-button').addEventListener('click', () => openStudentDialog());
  document.querySelector('#student-form').addEventListener('submit', saveStudent);
  document.querySelector('#bulk-edit-students').addEventListener('click', openBulkStudentDialog);
  document.querySelector('#bulk-student-form').addEventListener('submit', saveBulkStudents);
  document.querySelectorAll('[data-bulk-enable]').forEach((checkbox) => checkbox.addEventListener('change', () => {
    const field = checkbox.dataset.bulkEnable;
    document.querySelector('#bulk-student-form').elements[field].disabled = !checkbox.checked;
  }));
  document.querySelectorAll('[data-close-dialog]').forEach((button) => button.addEventListener('click', () => document.querySelector(`#${button.dataset.closeDialog}`).close()));
  document.querySelector('#excel-import-form').addEventListener('submit', (event) => submitImport(event, 'excel'));
  document.querySelector('#import-retry-form').addEventListener('submit', retryImportErrors);
  document.querySelector('#import-retry-form input[type="file"]').addEventListener('change', (event) => { document.querySelector('#import-retry-file-name').textContent = event.target.files[0]?.name || '请先下载错误行修正模板，修正后上传'; });
  document.querySelector('#related-import-form').addEventListener('submit', (event) => submitImport(event, 'related-info'));
  document.querySelector('#candidate-select-all').addEventListener('change', (event) => {
    document.querySelectorAll('#candidate-list [data-select-related-candidate]').forEach((checkbox) => {
      const candidateId = Number(checkbox.dataset.selectRelatedCandidate);
      checkbox.checked = event.currentTarget.checked;
      if (event.currentTarget.checked) state.selectedRelatedCandidateIds.add(candidateId); else state.selectedRelatedCandidateIds.delete(candidateId);
    });
    syncRelatedCandidateSelectionControls();
  });
  document.querySelector('#bulk-approve-related').addEventListener('click', bulkApproveRelatedCandidates);
  document.querySelector('#students-select-all').addEventListener('change', (event) => {
    state.students.forEach((student) => {
      if (event.currentTarget.checked) state.selectedStudentIds.add(student.id); else state.selectedStudentIds.delete(student.id);
    });
    document.querySelectorAll('#students-table [data-select-student]').forEach((checkbox) => { checkbox.checked = event.currentTarget.checked; });
    syncStudentSelectionControls();
  });
  document.querySelector('#export-button').addEventListener('click', () => openExportPreview({include_provenance:'true', student_ids:[...state.selectedStudentIds]}).catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#report-export-form').addEventListener('submit', (event) => {
    event.preventDefault();
    previewReportExport().catch((errorObject) => toast(errorObject.message, true));
  });
  document.querySelector('#report-export-preview').addEventListener('click', () => previewReportExport().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#confirm-export-preview').addEventListener('click', executePendingExport);
  document.querySelector('#export-preview-dialog').addEventListener('close', () => { state.pendingExport = null; });
  document.querySelector('#system-settings-form').addEventListener('submit', saveSystemSettings);
  document.querySelector('#check-system-update').addEventListener('click', () => loadSystemUpdate(true).then(() => toast('已完成 GitHub Release 检查。')).catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#system-update-config-form').addEventListener('submit', saveSystemUpdateConfiguration);
  document.querySelector('#system-update-execute-form').addEventListener('submit', startSystemUpdate);
  document.querySelector('#system-update-offline-form').addEventListener('submit', startOfflineSystemUpdate);
  document.querySelector('#open-high-risk-settings').addEventListener('click', openHighRiskSettings);
  document.querySelector('#high-risk-auth-form').addEventListener('submit', authorizeHighRiskSettings);
  document.querySelector('#high-risk-clear-students').addEventListener('click', clearAllStudentsHighRisk);
  document.querySelector('#high-risk-dialog').addEventListener('close', () => { state.highRiskApproval = null; });
  document.querySelector('#system-controls-form').addEventListener('submit', saveSystemControls);
  document.querySelector('#import-template-form').addEventListener('submit', saveImportTemplate);
  document.querySelector('#export-template-form').addEventListener('submit', saveExportTemplate);
  document.querySelector('#new-administrator-button').addEventListener('click', () => openAdministratorDialog());
  document.querySelector('#administrator-form').elements.role.addEventListener('change', (event) => {
    if (!state.currentAdministrator) applyDefaultAdministratorPermissions(event.currentTarget.value);
  });
  document.querySelector('#administrator-form').addEventListener('submit', saveAdministrator);
  document.querySelector('#data-scope-form').addEventListener('submit', saveDataScope);
  document.querySelector('#add-data-scope-rule').addEventListener('click', () => addDataScopeRule());
  document.querySelector('#account-security-form').addEventListener('submit', saveOwnPassword);
  document.querySelector('#setup-mfa-button').addEventListener('click', setupMfa);
  document.querySelector('#disable-mfa-button').addEventListener('click', disableMfa);
  document.querySelector('#create-backup-button').addEventListener('click', createBackup);
  document.querySelector('#refresh-system-info').addEventListener('click', () => loadSystemInfo().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#cleanup-exports-button').addEventListener('click', cleanupOldExports);
  document.querySelector('#refresh-ai-logs-button').addEventListener('click', () => loadAiConversationLogs().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-login-security-button').addEventListener('click', () => loadLoginSecurityEvents().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-audit-button').addEventListener('click', () => loadAuditLogs().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#verify-audit-button').addEventListener('click', verifyAudit);
  document.querySelector('#audit-filters').addEventListener('submit', (event) => { event.preventDefault(); loadAuditLogs().catch((errorObject) => toast(errorObject.message, true)); });
  document.querySelector('#run-quality-scan').addEventListener('click', () => loadQualityScan(true).then(() => toast('数据质量检查已完成')).catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-student-reminders').addEventListener('click', () => loadStudentReminders().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-duplicates').addEventListener('click', () => loadDuplicateStudents().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-monitoring').addEventListener('click', () => loadMonitoring().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#check-alerts').addEventListener('click', checkAlerts);
  document.querySelector('#run-ai-evaluation').addEventListener('click', runAiEvaluation);
  document.querySelector('#refresh-documents').addEventListener('click', () => loadDocuments().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-recycle-bin').addEventListener('click', () => loadRecycleBin().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-match-reviews').addEventListener('click', () => loadMatchReviews().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#refresh-tasks').addEventListener('click', () => loadTasks().catch((errorObject) => toast(errorObject.message, true)));
  document.querySelector('#ai-form').addEventListener('submit', askAssistant);
  document.querySelector('#clear-ai-context').addEventListener('click', clearAiConversation);
  document.querySelector('#ai-question').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      document.querySelector('#ai-form').requestSubmit();
    }
  });
}

window.addEventListener('pagehide', () => document.body.classList.add('page-exiting'));
window.addEventListener('pageshow', () => document.body.classList.remove('page-exiting'));

async function boot() {
  try {
    await loadUser();
    bindEvents();
    startIdleLogoutTimer();
    const loginNotice = window.sessionStorage.getItem('login-security-notice');
    if (loginNotice) { window.sessionStorage.removeItem('login-security-notice'); toast(loginNotice); }
    await Promise.all([refreshAll(), loadAiStatus(), loadAiConversation(), loadSavedStudentFilters()]);
    window.setInterval(loadAiStatus, 30000);
    refreshIcons();
  } catch (errorObject) {
    if (errorObject.message !== '登录已失效') toast(errorObject.message, true);
  }
}

boot();
