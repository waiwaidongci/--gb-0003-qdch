export type User={id:number;email:string;name:string;role:string};
export type Product={id:number;sku:string;name:string;category:string;price:number;cost:number;margin:number};
export type Batch={id:number;name:string;filename:string;checksum:string;receipt_count:number;created_at:string};
export type Receipt={id:number;reference:string;items:string[];batch_id:number};
export type Rule={antecedent:string[];consequent:string[];support_count:number;support:number;confidence:number;lift:number;bundle_price:number;gross_profit:number;margin:number};
export type Run={id:number;batch_id:number;name:string;status:string;min_support:number;min_confidence:number;min_lift:number;max_size:number;result:{receipt_count?:number;frequent_itemsets?:number;rules?:Rule[];checksum?:string;level_counts?:number[];method?:string};error?:string;created_at:string};
export type Proposal={id:number;run_id:number;name:string;status:string;note:string;rule:Rule;created_at:string};
export type Audit={id:number;actor:string;action:string;detail:object;created_at:string};
