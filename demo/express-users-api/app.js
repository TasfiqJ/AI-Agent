/**
 * Express Users API — demo target for test-guardian evaluation.
 */

const express = require('express');
const app = express();

app.use(express.json());

// In-memory store
let users = [];
let nextId = 1;

// List users
app.get('/api/users', (req, res) => {
  const { role } = req.query;
  let result = users;
  if (role) {
    result = users.filter(u => u.role === role);
  }
  res.json({ users: result, count: result.length });
});

// Create user
app.post('/api/users', (req, res) => {
  const { name, email, role } = req.body;
  if (!name || !email) {
    return res.status(400).json({ error: 'name and email are required' });
  }

  const user = {
    id: nextId++,
    name,
    email,
    role: role || 'user',
    createdAt: new Date().toISOString(),
  };
  users.push(user);
  res.status(201).json(user);
});

// Get user by ID
app.get('/api/users/:id', (req, res) => {
  const user = users.find(u => u.id === parseInt(req.params.id));
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  res.json(user);
});

// Update user
app.put('/api/users/:id', (req, res) => {
  const user = users.find(u => u.id === parseInt(req.params.id));
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  const { name, email, role } = req.body;
  if (name) user.name = name;
  if (email) user.email = email;
  if (role) user.role = role;

  res.json(user);
});

// Delete user
app.delete('/api/users/:id', (req, res) => {
  const index = users.findIndex(u => u.id === parseInt(req.params.id));
  if (index === -1) {
    return res.status(404).json({ error: 'User not found' });
  }
  users.splice(index, 1);
  res.json({ message: 'Deleted' });
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'express-users-api' });
});

if (require.main === module) {
  app.listen(3001, () => {
    console.log('Express Users API running on port 3001');
  });
}

module.exports = app;
