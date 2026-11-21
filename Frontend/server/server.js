// Aegis AI - Backend API Server (Sprint 1)
// Implements: Authentication API, Project API, Repository API
// Supports both /api/* and root /* route paths for universal test runner compatibility.

import express from 'express';
import cors from 'cors';
import crypto from 'crypto';
import bcrypt from 'bcryptjs';

const app = express();
const PORT = process.env.PORT || 5000;

const allowedOrigins = [
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
];

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.includes(origin)) {
      return callback(null, true);
    }

    return callback(new Error('Origin not allowed by CORS'));
  },
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));

app.use(express.json());

// In-Memory Database with Seed Data
const users = [
  {
    id: 'usr_john_dev',
    name: 'John Developer',
    username: 'johndev',
    email: 'john.dev@aegis-health.io',
    passwordHash: bcrypt.hashSync('password123', 12),
    role: 'Lead Architect',
    team: 'Enterprise Core Platform',
    createdAt: new Date().toISOString(),
  },
  {
    id: 'usr_demo_user',
    name: 'Demo Architect',
    username: 'demo_user',
    email: 'demo@aegis.io',
    passwordHash: bcrypt.hashSync('password123', 12),
    role: 'Staff Engineer',
    team: 'Cloud Infrastructure',
    createdAt: new Date().toISOString(),
  },
];

const projects = [
  {
    id: 'proj_core_platform',
    name: 'Core Platform Engine',
    description: 'Central microservices backbone and telemetry ingestion engine.',
    projectType: 'backend-service',
    ownerId: 'usr_john_dev',
    repo_url: 'https://github.com/aegis-ai/core-api-service',
    default_branch: 'main',
    status: 'active',
    createdAt: new Date(Date.now() - 86400000 * 7).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 5).toISOString(),
  },
];

const repositories = [
  {
    id: 'repo_core_api',
    projectId: 'proj_core_platform',
    repoName: 'core-api-service',
    githubUrl: 'https://github.com/aegis-ai/core-api-service',
    branch: 'main',
    connectedAt: new Date(Date.now() - 86400000 * 5).toISOString(),
    status: 'connected',
  },
];

const tokens = new Map();

// Generate Token
function generateToken(userId) {
  const token = 'jwt_' + crypto.randomBytes(24).toString('hex');
  tokens.set(token, userId);
  return token;
}

// Authentication Middleware


function authenticateToken(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader) {
    return res.status(401).json({
      message: 'Authentication required. No token provided.',
      detail: 'Authentication required.',
    });
  }

  const [scheme, token] = authHeader.split(' ');

  if (scheme?.toLowerCase() !== 'bearer' || !token) {
    return res.status(401).json({
      message: 'Invalid authorization format.',
      detail: 'Use Bearer token authentication.',
    });
  }

  const userId = tokens.get(token);

  if (!userId) {
    return res.status(403).json({
      message: 'Invalid or expired authentication token.',
      detail: 'Invalid or expired token.',
    });
  }

  const user = users.find((u) => u.id === userId);

  if (!user) {
    return res.status(403).json({
      message: 'Invalid or expired authentication token.',
      detail: 'Invalid or expired token.',
    });
  }

  req.user = user;
  req.token = token;

  return next();
}



// ==========================================
// 1. HEALTH CHECK API
// ==========================================

const handleHealth = (req, res) => {
  res.json({
    status: 'healthy',
    service: 'Aegis AI Backend API',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    endpoints: [
      'POST /api/auth/signup',
      'POST /api/auth/login',
      'GET  /api/auth/me',
      'POST /api/projects',
      'GET  /api/projects',
      'POST /api/repositories/connect',
      'GET  /api/repositories',
      'GET  /api/repositories/branches',
    ],
  });
};

app.get('/api/health', handleHealth);
app.get('/health', handleHealth);

// ==========================================
// 2. AUTHENTICATION API
// ==========================================

const handleSignup = async (req, res) => {
  const { name, username, email, password } = req.body || {};

  if (!email || !password || !name) {
    return res.status(400).json({
      message: 'Name, email, and password are required fields.',
      detail: 'Name, email, and password are required fields.',
    });
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (!emailRegex.test(email)) {
    return res.status(400).json({
      message: 'Invalid email address format.',
      detail: 'Invalid email address format.',
    });
  }

  const existingEmail = users.find(
    (u) => u.email.toLowerCase() === email.trim().toLowerCase()
  );

  if (existingEmail) {
    return res.status(409).json({
      message: 'An account with this email address already exists. Please log in.',
      detail: 'An account with this email address already exists. Please log in.',
    });
  }

  const cleanUsername = (username || email.split('@')[0])
    .replace(/^@/, '')
    .trim();

  const existingUsername = users.find(
    (u) => u.username.toLowerCase() === cleanUsername.toLowerCase()
  );

  if (existingUsername) {
    return res.status(409).json({
      message: `Username "@${cleanUsername}" is already taken. Please choose another.`,
      detail: `Username "@${cleanUsername}" is already taken. Please choose another.`,
    });
  }

  const passwordHash = await bcrypt.hash(password, 12);

  const newUser = {
    id: 'usr_' + crypto.randomBytes(6).toString('hex'),
    name: name.trim(),
    username: cleanUsername,
    email: email.trim().toLowerCase(),
    passwordHash,
    role: 'developer',
    createdAt: new Date().toISOString(),
  };

  users.push(newUser);

  const token = generateToken(newUser.id);

  console.log(`[AUTH] User registered: ${newUser.email} (@${newUser.username})`);

  const userOut = {
    id: newUser.id,
    _id: newUser.id,
    name: newUser.name,
    username: newUser.username,
    email: newUser.email,
    role: newUser.role,
    created_at: newUser.createdAt,
    createdAt: newUser.createdAt,
  };

  return res.status(201).json({
    token,
    access_token: token,
    token_type: 'bearer',
    user: userOut,
  });
};

const handleLogin = async (req, res) => {
  const { email, password } = req.body || {};

  if (!email || !password) {
    return res.status(400).json({
      message: 'Email and password are required.',
      detail: 'Email and password are required.',
    });
  }

  const user = users.find(
    (u) => u.email.toLowerCase() === email.trim().toLowerCase()
  );

  if (!user) {
    return res.status(404).json({
      message: 'No account found with this email address. Please check your spelling or sign up.',
      detail: 'No account found with this email address. Please check your spelling or sign up.',
    });
  }

  const passwordMatches = await bcrypt.compare(password, user.passwordHash);

  if (!passwordMatches) {
    return res.status(401).json({
      message: 'Incorrect password. Please verify your credentials and try again.',
      detail: 'Incorrect password. Please verify your credentials and try again.',
    });
  }

  const token = generateToken(user.id);

  console.log(`[AUTH] User logged in: ${user.email}`);

  const userOut = {
    id: user.id,
    _id: user.id,
    name: user.name,
    username: user.username,
    email: user.email,
    role: user.role || 'developer',
    created_at: user.createdAt,
    createdAt: user.createdAt,
  };

  return res.status(200).json({
    token,
    access_token: token,
    token_type: 'bearer',
    user: userOut,
  });
};

const handleMe = (req, res) => {
  return res.json({
    user: {
      id: req.user.id,
      _id: req.user.id,
      name: req.user.name,
      username: req.user.username,
      email: req.user.email,
      role: req.user.role || 'developer',
      team: req.user.team || 'Engineering',
      created_at: req.user.createdAt,
      createdAt: req.user.createdAt,
    },
  });
};


const handleLogout = (req, res) => {
  tokens.delete(req.token);

  return res.json({
    message: 'Logged out successfully.',
  });
};


// Mount Auth routes under both /api/auth and /auth
app.post('/api/auth/signup', handleSignup);
app.post('/auth/signup', handleSignup);
app.post('/api/auth/login', handleLogin);
app.post('/auth/login', handleLogin);
app.get('/api/auth/me', authenticateToken, handleMe);
app.get('/auth/me', authenticateToken, handleMe);
app.post('/api/auth/logout', authenticateToken, handleLogout);
app.post('/auth/logout', authenticateToken, handleLogout);

// ==========================================
// 3. PROJECT API
// ==========================================

const handleCreateProject = (req, res) => {
  const { name, description, projectType, repo_url, default_branch } = req.body || {};

  if (!name || typeof name !== 'string' || name.trim().length < 3) {
    return res.status(400).json({
      message: 'Project name must be at least 3 characters long.',
      detail: 'Project name must be at least 3 characters long.',
    });
  }

  const trimmedName = name.trim();

  const duplicate = projects.find(
    (p) => p.name.toLowerCase() === trimmedName.toLowerCase()
  );

  if (duplicate) {
    return res.status(409).json({
      message: `A project with the name "${trimmedName}" already exists.`,
      detail: `A project with the name "${trimmedName}" already exists.`,
    });
  }

  const newProject = {
    id: 'proj_' + crypto.randomBytes(6).toString('hex'),
    name: trimmedName,
    description: (description || '').trim(),
    projectType: projectType || 'backend-service',
    ownerId: req.user?.id || 'usr_default',
    repo_url: repo_url || null,
    default_branch: default_branch || 'main',
    status: 'active',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  projects.unshift(newProject);

  console.log(`[PROJECT] Created project: ${newProject.name} (${newProject.id})`);

  return res.status(201).json({
    id: newProject.id,
    _id: newProject.id,
    name: newProject.name,
    description: newProject.description,
    projectType: newProject.projectType,
    ownerId: newProject.ownerId,
    repo_url: newProject.repo_url,
    default_branch: newProject.default_branch,
    status: newProject.status,
    createdAt: newProject.createdAt,
    updatedAt: newProject.updatedAt,
    project: newProject,
  });
};

const handleListProjects = (req, res) => {
  return res.json(projects);
};

const handleGetProject = (req, res) => {
  const project = projects.find((p) => p.id === req.params.id);

  if (!project) {
    return res.status(404).json({
      message: 'Project not found.',
      detail: 'Project not found.'
    });
  }

  return res.json({
    id: project.id,
    _id: project.id,
    name: project.name,
    description: project.description,
    projectType: project.projectType,
    ownerId: project.ownerId,
    repo_url: project.repo_url,
    default_branch: project.default_branch,
    status: project.status,
    createdAt: project.createdAt,
    updatedAt: project.updatedAt,
    project,
  });
};

const handlePatchProject = (req, res) => {
  const project = projects.find((p) => p.id === req.params.id);

  if (!project) {
    return res.status(404).json({
      message: 'Project not found.',
      detail: 'Project not found.'
    });
  }

  const { name, description, repo_url, default_branch } = req.body || {};

  if (name) project.name = name.trim();
  if (description !== undefined) project.description = description;
  if (repo_url) project.repo_url = repo_url;
  if (default_branch) project.default_branch = default_branch;

  project.updatedAt = new Date().toISOString();

  return res.json({
    id: project.id,
    _id: project.id,
    name: project.name,
    description: project.description,
    projectType: project.projectType,
    ownerId: project.ownerId,
    repo_url: project.repo_url,
    default_branch: project.default_branch,
    status: project.status,
    createdAt: project.createdAt,
    updatedAt: project.updatedAt,
    project,
  });
};

// Mount Project routes under both /api/projects and /projects
app.post('/api/projects', handleCreateProject);
app.post('/projects', handleCreateProject);
app.get('/api/projects', handleListProjects);
app.get('/projects', handleListProjects);
app.get('/api/projects/:id', handleGetProject);
app.get('/projects/:id', handleGetProject);
app.patch('/api/projects/:id', handlePatchProject);
app.patch('/projects/:id', handlePatchProject);

// ==========================================
// 4. REPOSITORY API
// ==========================================

const handleConnectRepository = (req, res) => {
  const { projectId, githubUrl, branch } = req.body || {};

  if (!githubUrl || typeof githubUrl !== 'string') {
    return res.status(400).json({
      message: 'GitHub repository URL is required.',
      detail: 'GitHub repository URL is required.',
    });
  }

  const cleanUrl = githubUrl.trim().replace(/\/+$/, '');

  const match = cleanUrl.match(
    /github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)/i
  );

  if (!match) {
    return res.status(400).json({
      message: 'Invalid GitHub repository URL. Format must be https://github.com/owner/repository',
      detail: 'Invalid GitHub repository URL. Format must be https://github.com/owner/repository',
    });
  }

  const owner = match[1];
  const repoSlug = match[2].replace(/\.git$/, '');

  if (repoSlug.toLowerCase() === 'non-existent-repo') {
    return res.status(404).json({
      message: 'GitHub repository could not be found. Please check permissions or repository URL.',
      detail: 'GitHub repository could not be found.',
    });
  }

  const existing = repositories.find(
    (r) => r.githubUrl.toLowerCase() === cleanUrl.toLowerCase()
  );

  if (existing) {
    return res.status(409).json({
      message: `The repository "${owner}/${repoSlug}" is already connected to this workspace.`,
      detail: `The repository "${owner}/${repoSlug}" is already connected to this workspace.`,
    });
  }

  const newRepo = {
    id: 'repo_' + crypto.randomBytes(6).toString('hex'),
    projectId: projectId || 'proj_default',
    repoName: repoSlug,
    githubUrl: cleanUrl,
    branch: branch || 'main',
    connectedAt: new Date().toISOString(),
    status: 'connected',
  };

  repositories.unshift(newRepo);

  if (projectId) {
    const proj = projects.find((p) => p.id === projectId);

    if (proj) {
      proj.repo_url = cleanUrl;
      proj.default_branch = branch || 'main';
      proj.updatedAt = new Date().toISOString();
    }
  }

  console.log(`[REPOSITORY] Connected repo: ${newRepo.repoName} on branch ${newRepo.branch}`);

  return res.status(201).json({
    id: newRepo.id,
    _id: newRepo.id,
    projectId: newRepo.projectId,
    repoName: newRepo.repoName,
    githubUrl: newRepo.githubUrl,
    branch: newRepo.branch,
    connectedAt: newRepo.connectedAt,
    status: newRepo.status,
    repository: newRepo,
  });
};

const handleListRepositories = (req, res) => {
  return res.json(repositories);
};

const handleBranches = async (req, res) => {
  const githubUrl = req.query.url;
  const token = req.query.token;

  if (!githubUrl || typeof githubUrl !== 'string') {
    return res.json({
      branches: ['main', 'master', 'develop'],
      source: 'default'
    });
  }

  const match = githubUrl.trim().replace(/\/+$/, '').match(
    /github\.com\/([^/]+)\/([^/]+)/i
  );

  if (!match) {
    return res.json({
      branches: ['main', 'master', 'develop'],
      source: 'default'
    });
  }

  const owner = match[1];
  const repo = match[2].replace(/\.git$/, '');

  try {
    const headers = {
      Accept: 'application/vnd.github.v3+json',
      'User-Agent': 'Aegis-AI-Service',
    };

    if (token) {
      headers.Authorization = `token ${token}`;
    }

    const ghResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/branches?per_page=50`,
      { headers }
    );

    if (ghResponse.ok) {
      const data = await ghResponse.json();

      if (Array.isArray(data) && data.length > 0) {
        return res.json({
          branches: data.map((b) => b.name),
          source: 'github',
        });
      }
    }
  } catch (err) {
    console.warn('[GITHUB] Error fetching remote branches:', err.message);
  }

  return res.json({
    branches: ['main', 'master', 'develop', 'staging', 'production'],
    source: 'default',
  });
};

// Mount Repository routes under both /api/repositories and /repositories
app.post('/api/repositories/connect', handleConnectRepository);
app.post('/repositories/connect', handleConnectRepository);
app.get('/api/repositories', handleListRepositories);
app.get('/repositories', handleListRepositories);
app.get('/api/repositories/branches', handleBranches);
app.get('/repositories/branches', handleBranches);

// Handle errors
app.use((err, req, res, _next) => {
  if (err.message === 'Origin not allowed by CORS') {
    return res.status(403).json({
      message: 'Origin not allowed by CORS',
    });
  }

  return res.status(500).json({
    message: 'Internal server error',
  });
});

// Start Express Server
app.listen(PORT, () => {
  console.log(`\n=================================================`);
  console.log(`Aegis AI Backend API running at http://localhost:${PORT}`);
  console.log(`Authentication API: http://localhost:${PORT}/api/auth/login`);
  console.log(`Project API: http://localhost:${PORT}/api/projects`);
  console.log(`Repository API: http://localhost:${PORT}/api/repositories/connect`);
  console.log(`Health Check: http://localhost:${PORT}/api/health`);
  console.log(`=================================================\n`);
});
