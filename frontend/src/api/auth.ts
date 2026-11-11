import {post,request} from './client';
import type {User} from '../types/domain';
export const authApi={login:(email:string,password:string)=>post('/auth/login',{email,password}),me:()=>request<User>('/auth/me')};
