import {request,post} from './client';
import type {Product,Batch,Receipt} from '../types/domain';
export const catalogApi={products:()=>request<Product[]>('/products'),batches:()=>request<Batch[]>('/batches'),receipts:(id:number)=>request<Receipt[]>('/batches/'+id+'/receipts'),createBatch:(data:any)=>post('/batches',data),createProduct:(data:any)=>post('/products',data)};
