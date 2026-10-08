import {describe, it} from 'vitest';
import {projectReceivables, receivablesFor} from '../src/receivables';
import {receivablesCases} from './receivables-cases';
describe('client receivables', () => {
  for (const entry of receivablesCases) it(entry.name, () => entry.run(projectReceivables, receivablesFor));
});
