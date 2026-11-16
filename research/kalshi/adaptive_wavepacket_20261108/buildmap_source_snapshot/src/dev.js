// Browser-QA entry point. The normal CLI remains the user-facing local launcher.
import { startServer } from './server.js';
const args = process.argv.slice(2);
const option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const port = Number(option('--port', '4173'));
if (!Number.isInteger(port) || port < 0 || port > 65535) throw Error('Invalid preview port.');
startServer({ root: process.cwd(), host: option('--host', '127.0.0.1'), port });
