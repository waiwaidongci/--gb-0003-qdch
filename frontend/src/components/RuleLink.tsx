import type {Rule,Product} from '../types/domain';
import {names,pct,decimal} from '../utils/format';
export function RuleLink({rule,products}:{rule:Rule;products:Product[]}){return <div className="rule-link"><div><small>当篮子包含</small><strong>{names(rule.antecedent,products)}</strong></div><span className="rule-arrow">→<small>{pct(rule.confidence)}</small></span><div><small>同时出现</small><strong>{names(rule.consequent,products)}</strong></div><aside><b>{decimal(rule.lift)}×</b><small>相对自然基率</small></aside></div>}
