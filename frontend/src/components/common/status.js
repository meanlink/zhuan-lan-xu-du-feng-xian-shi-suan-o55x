import {JobStatus} from '../../constants/enums.js';
import {esc} from '../../utils/dom.js';
export const status=(v,map=JobStatus)=>'<span class="status '+esc(v)+'">'+esc(map[v]||v)+'</span>';
