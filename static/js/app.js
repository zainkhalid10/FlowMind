// Global API Configuration
const API_BASE = (window.location && window.location.origin)
  ? String(window.location.origin).replace(/\/$/, '')
  : 'http://localhost:8000';
const THEME_KEY = 'fm_theme';

// ==================== Token Management ====================
function getToken() {
  return localStorage.getItem('fm_token') || localStorage.getItem('access_token');
}

function setToken(token) {
  localStorage.setItem('fm_token', token);
  localStorage.setItem('access_token', token);
}

function getRole() {
  const storedRole = (localStorage.getItem('fm_role') || '').toLowerCase();
  const token = getToken();
  if (!token) {
    return storedRole;
  }

  // Decode JWT payload role as a safe fallback when localStorage role is stale.
  const tokenRole = getRoleFromToken(token);
  if (tokenRole) {
    if (storedRole !== tokenRole) {
      setRole(tokenRole);
    }
    return tokenRole;
  }

  return storedRole;
}

function setRole(role) {
  if (!role) {
    localStorage.removeItem('fm_role');
    return;
  }
  localStorage.setItem('fm_role', String(role).toLowerCase());
}

function getRoleFromToken(token) {
  try {
    const parts = String(token || '').split('.');
    if (parts.length < 2) {
      return '';
    }
    let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
      base64 += '=';
    }
    const payload = JSON.parse(atob(base64));
    return String(payload.role || '').toLowerCase();
  } catch (e) {
    return '';
  }
}

function clearToken() {
  localStorage.removeItem('fm_token');
  localStorage.removeItem('access_token');
  localStorage.removeItem('fm_role');
  localStorage.removeItem('fm_name');
  localStorage.removeItem('fm_assigned_file');
}

// ==================== Auth Check ====================
function requireAuth() {
  if (!getToken()) {
    window.location.href = '/login.html';
    return;
  }

  const role = getRole();
  const path = (window.location.pathname || '').toLowerCase();
  const isClientPortal = path.includes('client_review.html') || path.includes('/client-review');

  if (role === 'client' && !isClientPortal) {
    window.location.href = '/client-review';
    return;
  }

  if (role && role !== 'client' && isClientPortal) {
    window.location.href = '/dashboard';
  }
}

// ==================== API Fetch Helper ====================
async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
    ...(options.headers || {})
  };

  const response = await fetch(API_BASE + path, {
    ...options,
    headers
  });

  if (response.status === 401) {
    clearToken();
    window.location.href = '/login.html';
  }

  return response;
}

// ==================== Notifications ====================
function showToast(message, type = '') {
  let toast = document.getElementById('fm-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'fm-toast';
    document.body.appendChild(toast);
  }
  
  toast.textContent = message;
  toast.className = 'fm-toast show ' + type;
  
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

// ==================== Navigation ====================
function setActivePage(pageName) {
  document.querySelectorAll('.fm-nav-item').forEach(element => {
    if (element.dataset.page === pageName) {
      element.classList.add('active');
    } else {
      element.classList.remove('active');
    }
  });
}

// ==================== User Management ====================
async function loadUser() {
  try {
    let response = await apiFetch('/api/me');
    if (!response.ok) {
      response = await apiFetch('/auth/me');
    }
    if (response.ok) {
      const userData = await response.json();
      const displayName = userData.name || userData.username || userData.email || 'User';
      if (userData.role) {
        setRole(userData.role);
      }
      localStorage.setItem('fm_name', displayName);
      
      // Set initials
      const initials = displayName
        .split(' ')
        .map(word => word[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
      
      const initialsElement = document.getElementById('userInitials');
      if (initialsElement) {
        initialsElement.textContent = initials;
      }
      
      // Set name
      const nameElement = document.getElementById('userName');
      if (nameElement) {
        nameElement.textContent = displayName;
      }

      const roleElement = document.querySelector('.fm-user-role');
      if (roleElement && userData.role) {
        const normalizedRole = String(userData.role).replace('_', ' ');
        roleElement.textContent = normalizedRole.charAt(0).toUpperCase() + normalizedRole.slice(1);
      }
    }
  } catch (error) {
    console.error('Error loading user:', error);
  }
}

// ==================== Theme Management ====================
function getPreferredTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === 'light' || stored === 'dark') {
    return stored;
  }
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  return prefersDark ? 'dark' : 'light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  syncThemeToggleIcon();
}

function syncThemeToggleIcon() {
  const button = document.getElementById('fmThemeToggle');
  if (!button) {
    return;
  }
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  button.textContent = theme === 'dark' ? '☀' : '🌙';
  button.setAttribute('title', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
}

function injectThemeToggle() {
  if (document.getElementById('fmThemeToggle')) {
    syncThemeToggleIcon();
    return;
  }
  const sidebarUser = document.querySelector('.fm-sidebar-user');
  if (!sidebarUser) {
    return;
  }
  const button = document.createElement('button');
  button.id = 'fmThemeToggle';
  button.type = 'button';
  button.className = 'fm-theme-toggle';
  button.addEventListener('click', toggleTheme);
  sidebarUser.appendChild(button);
  syncThemeToggleIcon();
}

// ==================== Logout ====================
function logout() {
  clearToken();
  window.location.href = '/';
}

// ==================== Document Ready ====================
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(getPreferredTheme());
  injectThemeToggle();

  // Auto-load user if authenticated
  if (getToken() && document.getElementById('userName')) {
    loadUser();
  }
});
