import crypto from 'crypto';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-me';
const TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30;

export function signSessionToken(userId, scopes = []) {
  return jwt.sign(
    { sub: userId, scopes },
    JWT_SECRET,
    { algorithm: 'HS256', expiresIn: TOKEN_TTL_SECONDS }
  );
}

export function verifySessionToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch (err) {
    return null;
  }
}

export function authMiddleware(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.replace(/^Bearer\s+/i, '');
  const payload = verifySessionToken(token);
  if (!payload) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  req.user = payload;
  next();
}

export function compareWebhookSignature(rawBody, signature) {
  const expected = crypto
    .createHmac('sha256', process.env.WEBHOOK_SECRET || '')
    .update(rawBody)
    .digest('hex');
  return expected === signature;
}
