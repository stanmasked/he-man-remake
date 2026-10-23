#include "heman_textured_quad_reference.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define HM_MAX_ABS_COORDINATE 10000000.0

typedef struct hm_prepared_quad {
    const hm_symbol_frame_packet *packet;
    const hm_texture_reference_binding *texture;
    double xy[8];
    int32_t min_x,max_x,min_y,max_y;
    double ex_x,ex_y,ey_x,ey_y,determinant;
    uint32_t source_factor,destination_factor;
} hm_prepared_quad;

static int hm_finite_bounded(double x) { return isfinite(x) && fabs(x)<=HM_MAX_ABS_COORDINATE; }
static int hm_factor_valid(uint32_t f,int source) {
    switch(f) {
        case HM_GL_ZERO: case HM_GL_ONE: case HM_GL_SRC_COLOR:
        case HM_GL_ONE_MINUS_SRC_COLOR: case HM_GL_SRC_ALPHA:
        case HM_GL_ONE_MINUS_SRC_ALPHA: case HM_GL_DST_ALPHA:
        case HM_GL_ONE_MINUS_DST_ALPHA: case HM_GL_DST_COLOR:
        case HM_GL_ONE_MINUS_DST_COLOR: return 1;
        case HM_GL_SRC_ALPHA_SATURATE: return source;
        default: return 0;
    }
}
static const hm_texture_reference_binding *hm_find_binding(
    const hm_texture_reference_binding *items,size_t count,int32_t slot) {
    size_t i;
    for(i=0u;i<count;++i) if(items[i].texture_slot==slot) return &items[i];
    return NULL;
}
static hm_texture_reference_status hm_validate_bindings(
    const hm_texture_reference_binding *items,size_t count) {
    size_t i,j;
    if(count>HM_TEXTURE_REF_MAX_BINDINGS) return HM_TEXTURE_REFERENCE_LIMIT_EXCEEDED;
    if(count!=0u && items==NULL) return HM_TEXTURE_REFERENCE_INVALID_ARGUMENT;
    for(i=0u;i<count;++i) {
        const hm_texture_reference_binding *b=&items[i];
        size_t bytes;
        if(b->texture_slot<0 || b->width==0u || b->height==0u || b->rgba==NULL)
            return HM_TEXTURE_REFERENCE_INVALID_TEXTURE;
        if((size_t)b->width>(size_t)HM_TEXTURE_REF_MAX_TEXTURE_BYTES/4u/(size_t)b->height)
            return HM_TEXTURE_REFERENCE_LIMIT_EXCEEDED;
        bytes=(size_t)b->width*(size_t)b->height*4u;
        if(bytes>(size_t)HM_TEXTURE_REF_MAX_TEXTURE_BYTES || b->rgba_size!=bytes ||
           (b->wrap_s_code!=0 && b->wrap_s_code!=1) ||
           (b->wrap_t_code!=0 && b->wrap_t_code!=1) || b->filter_mode_code!=0)
            return HM_TEXTURE_REFERENCE_INVALID_TEXTURE;
        for(j=0u;j<i;++j)
            if(items[j].texture_slot==b->texture_slot) return HM_TEXTURE_REFERENCE_INVALID_TEXTURE;
    }
    return HM_TEXTURE_REFERENCE_OK;
}
static hm_texture_reference_status hm_validate_packet(
    const hm_symbol_frame_packet *p,const hm_symbol_frame_packet *previous) {
    size_t i;
    if(p==NULL || (previous!=NULL && p->source_order<=previous->source_order))
        return HM_TEXTURE_REFERENCE_INVALID_PACKET;
    if((p->front_face_flip!=0 && p->front_face_flip!=1) ||
       p->blend_override_enabled<0 || p->blend_override_enabled>1)
        return HM_TEXTURE_REFERENCE_INVALID_PACKET;
    for(i=0u;i<8u;++i)
        if(!hm_finite_bounded((double)p->xy[i]) || !hm_finite_bounded((double)p->uv[i]))
            return HM_TEXTURE_REFERENCE_NONFINITE;
    for(i=0u;i<4u;++i)
        if(!isfinite((double)p->rgba[i]) || p->rgba[i]<0.0f || p->rgba[i]>1.0f)
            return HM_TEXTURE_REFERENCE_INVALID_PACKET;
    if(p->uv[0]!=p->uv[2] || p->uv[1]!=p->uv[7] ||
       p->uv[3]!=p->uv[5] || p->uv[4]!=p->uv[6])
        return HM_TEXTURE_REFERENCE_INVALID_PACKET;
    if(p->blend_override_enabled==0) {
        if(p->blend_source!=-1 || p->blend_destination!=-1)
            return HM_TEXTURE_REFERENCE_INVALID_PACKET;
    } else if(p->blend_source<0 || p->blend_destination<0 ||
       !hm_factor_valid((uint32_t)p->blend_source,1) ||
       !hm_factor_valid((uint32_t)p->blend_destination,0)) {
        return HM_TEXTURE_REFERENCE_INVALID_PACKET;
    }
    return HM_TEXTURE_REFERENCE_OK;
}
static int32_t hm_clamp_edge(double v,uint32_t limit,int up) {
    const double rounded=up?ceil(v):floor(v);
    if(rounded<=0.0) return 0;
    if(rounded>=(double)limit) return (int32_t)limit;
    return (int32_t)rounded;
}
static hm_texture_reference_status hm_prepare(
    hm_prepared_quad *q,const hm_symbol_frame_packet *p,
    const hm_texture_reference_binding *texture,
    const hm_texture_reference_projection *proj,uint32_t width,uint32_t height) {
    double minx,maxx,miny,maxy,magnitude=1.0,expx,expy,tolerance;
    size_t i;
    for(i=0u;i<4u;++i) {
        const double x=p->xy[i*2u],y=p->xy[i*2u+1u];
        const double px=proj->m00*x+proj->m01*y+proj->tx;
        const double py=proj->m10*x+proj->m11*y+proj->ty;
        if(!hm_finite_bounded(px)||!hm_finite_bounded(py)) return HM_TEXTURE_REFERENCE_NONFINITE;
        q->xy[i*2u]=px; q->xy[i*2u+1u]=py;
    }
    minx=maxx=q->xy[0]; miny=maxy=q->xy[1];
    for(i=0u;i<4u;++i) {
        const double x=q->xy[i*2u],y=q->xy[i*2u+1u];
        if(x<minx)minx=x; if(x>maxx)maxx=x;
        if(y<miny)miny=y; if(y>maxy)maxy=y;
        if(fabs(x)>magnitude)magnitude=fabs(x);
        if(fabs(y)>magnitude)magnitude=fabs(y);
    }
    expx=q->xy[6]+q->xy[2]-q->xy[0]; expy=q->xy[7]+q->xy[3]-q->xy[1];
    tolerance=1e-5+2e-6*magnitude;
    if(fabs(q->xy[4]-expx)>tolerance||fabs(q->xy[5]-expy)>tolerance)
        return HM_TEXTURE_REFERENCE_NON_AFFINE_QUAD;
    q->min_x=hm_clamp_edge(minx,width,0); q->max_x=hm_clamp_edge(maxx,width,1);
    q->min_y=hm_clamp_edge(miny,height,0); q->max_y=hm_clamp_edge(maxy,height,1);
    q->ex_x=q->xy[6]-q->xy[0]; q->ex_y=q->xy[7]-q->xy[1];
    q->ey_x=q->xy[2]-q->xy[0]; q->ey_y=q->xy[3]-q->xy[1];
    q->determinant=q->ex_x*q->ey_y-q->ex_y*q->ey_x;
    q->packet=p; q->texture=texture;
    return HM_TEXTURE_REFERENCE_OK;
}
static int64_t hm_nearest_index(double coord,uint32_t size,int32_t wrap) {
    int64_t idx=(int64_t)floor(coord*(double)size);
    if(wrap==0) {
        if(idx<0)return 0;
        if((uint64_t)idx>=(uint64_t)size)return (int64_t)size-1;
        return idx;
    }
    idx%=(int64_t)size; if(idx<0)idx+=(int64_t)size;
    return idx;
}
static double hm_factor(uint32_t f,const double src[4],const double dst[4],size_t c) {
    switch(f) {
        case HM_GL_ZERO:return 0.0; case HM_GL_ONE:return 1.0;
        case HM_GL_SRC_COLOR:return src[c]; case HM_GL_ONE_MINUS_SRC_COLOR:return 1.0-src[c];
        case HM_GL_DST_COLOR:return dst[c]; case HM_GL_ONE_MINUS_DST_COLOR:return 1.0-dst[c];
        case HM_GL_SRC_ALPHA:return src[3]; case HM_GL_ONE_MINUS_SRC_ALPHA:return 1.0-src[3];
        case HM_GL_DST_ALPHA:return dst[3]; case HM_GL_ONE_MINUS_DST_ALPHA:return 1.0-dst[3];
        case HM_GL_SRC_ALPHA_SATURATE:return c==3u?1.0:fmin(src[3],1.0-dst[3]);
        default:return 0.0;
    }
}
static uint8_t hm_to_byte(double v) {
    double n;
    if(v<=0.0)return 0u; if(v>=1.0)return 255u;
    n=floor(v*255.0+0.5); if(n<=0.0)return 0u; if(n>=255.0)return 255u;
    return (uint8_t)n;
}
static void hm_sample(const hm_texture_reference_binding *t,double u,double v,uint8_t out[4]) {
    const int64_t x=hm_nearest_index(u,t->width,t->wrap_s_code);
    const int64_t y=hm_nearest_index(v,t->height,t->wrap_t_code);
    const size_t at=((size_t)y*(size_t)t->width+(size_t)x)*4u;
    memcpy(out,t->rgba+at,4u);
}
static void hm_blend(uint8_t *dst_bytes,const uint8_t texel[4],const float rgba[4],
                     uint32_t sfactor,uint32_t dfactor) {
    double src[4],dst[4]; size_t c;
    for(c=0u;c<4u;++c) {
        src[c]=((double)texel[c]/255.0)*(double)rgba[c];
        if(src[c]<0.0)src[c]=0.0; if(src[c]>1.0)src[c]=1.0;
        dst[c]=(double)dst_bytes[c]/255.0;
    }
    for(c=0u;c<4u;++c)
        dst_bytes[c]=hm_to_byte(src[c]*hm_factor(sfactor,src,dst,c)+
                                dst[c]*hm_factor(dfactor,src,dst,c));
}

hm_texture_reference_status hm_textured_quad_reference_render(
    const hm_texture_reference_draw *draws,size_t draw_count,
    const hm_texture_reference_binding *bindings,size_t binding_count,
    uint32_t width,uint32_t height,size_t stride_bytes,
    const hm_texture_reference_projection *projection,
    const hm_texture_reference_blend *frame_blend,const uint8_t clear_rgba[4],
    uint8_t *out_pixels,size_t out_capacity,hm_texture_reference_stats *out_stats) {
    hm_prepared_quad *prepared=NULL; uint8_t *staged=NULL;
    size_t packed_size,row_bytes,needed,budget=0u,i,py,px,covered=0u,samples=0u;
    hm_texture_reference_status status=HM_TEXTURE_REFERENCE_OK;
    if(projection==NULL||frame_blend==NULL||clear_rgba==NULL||out_pixels==NULL||
       out_stats==NULL||(draw_count!=0u&&draws==NULL))
        return HM_TEXTURE_REFERENCE_INVALID_ARGUMENT;
    if(draw_count>HM_TEXTURE_REF_MAX_PACKETS)return HM_TEXTURE_REFERENCE_LIMIT_EXCEEDED;
    if(width==0u||height==0u||width>HM_TEXTURE_REF_MAX_FRAME_PIXELS/height)
        return HM_TEXTURE_REFERENCE_LIMIT_EXCEEDED;
    if(!hm_factor_valid(frame_blend->source_factor,1)||
       !hm_factor_valid(frame_blend->destination_factor,0))
        return HM_TEXTURE_REFERENCE_INVALID_STATE;
    if(!hm_finite_bounded(projection->m00)||!hm_finite_bounded(projection->m01)||
       !hm_finite_bounded(projection->tx)||!hm_finite_bounded(projection->m10)||
       !hm_finite_bounded(projection->m11)||!hm_finite_bounded(projection->ty))
        return HM_TEXTURE_REFERENCE_INVALID_STATE;
    status=hm_validate_bindings(bindings,binding_count);
    if(status!=HM_TEXTURE_REFERENCE_OK)return status;
    row_bytes=(size_t)width*4u;
    if(stride_bytes<row_bytes||(size_t)(height-1u)>((size_t)-1-row_bytes)/stride_bytes)
        return HM_TEXTURE_REFERENCE_INVALID_ARGUMENT;
    needed=(size_t)(height-1u)*stride_bytes+row_bytes;
    if(out_capacity<needed)return HM_TEXTURE_REFERENCE_INVALID_ARGUMENT;
    packed_size=(size_t)width*(size_t)height*4u;
    if(draw_count!=0u) {
        prepared=(hm_prepared_quad *)calloc(draw_count,sizeof *prepared);
        if(prepared==NULL)return HM_TEXTURE_REFERENCE_ALLOCATION_FAILED;
    }
    for(i=0u;i<draw_count;++i) {
        const hm_symbol_frame_packet *p=draws[i].packet;
        const hm_texture_reference_binding *texture;
        size_t area;
        if(draws[i].texture_slot<0) { status=HM_TEXTURE_REFERENCE_INVALID_PACKET; goto cleanup; }
        status=hm_validate_packet(p,i==0u?NULL:draws[i-1u].packet);
        if(status!=HM_TEXTURE_REFERENCE_OK)goto cleanup;
        texture=hm_find_binding(bindings,binding_count,draws[i].texture_slot);
        if(texture==NULL) { status=HM_TEXTURE_REFERENCE_MISSING_TEXTURE; goto cleanup; }
        status=hm_prepare(&prepared[i],p,texture,projection,width,height);
        if(status!=HM_TEXTURE_REFERENCE_OK)goto cleanup;
        if(p->blend_override_enabled) {
            prepared[i].source_factor=(uint32_t)p->blend_source;
            prepared[i].destination_factor=(uint32_t)p->blend_destination;
        } else {
            prepared[i].source_factor=frame_blend->source_factor;
            prepared[i].destination_factor=frame_blend->destination_factor;
        }
        if(prepared[i].determinant!=0.0) {
            area=(size_t)(prepared[i].max_x-prepared[i].min_x)*
                 (size_t)(prepared[i].max_y-prepared[i].min_y);
            if(area>(size_t)HM_TEXTURE_REF_MAX_SAMPLE_ATTEMPTS-budget) {
                status=HM_TEXTURE_REFERENCE_LIMIT_EXCEEDED; goto cleanup;
            }
            budget+=area;
        }
    }
    staged=(uint8_t *)malloc(packed_size);
    if(staged==NULL) { status=HM_TEXTURE_REFERENCE_ALLOCATION_FAILED; goto cleanup; }
    for(i=0u;i<(size_t)width*(size_t)height;++i)memcpy(staged+i*4u,clear_rgba,4u);
    for(i=0u;i<draw_count;++i) {
        const hm_prepared_quad *q=&prepared[i]; size_t local_samples=0u;
        double p0x,p0y;
        if(q->determinant==0.0||q->min_x>=q->max_x||q->min_y>=q->max_y)continue;
        p0x=q->xy[0]; p0y=q->xy[1];
        for(py=(size_t)q->min_y;py<(size_t)q->max_y;++py) {
            const double dy=(double)py+0.5-p0y;
            for(px=(size_t)q->min_x;px<(size_t)q->max_x;++px) {
                const double dx=(double)px+0.5-p0x;
                const double s=(dx*q->ey_y-dy*q->ey_x)/q->determinant;
                const double t=(q->ex_x*dy-q->ex_y*dx)/q->determinant;
                double u,v; uint8_t texel[4]; size_t at;
                if(s<0.0||s>=1.0||t<0.0||t>=1.0)continue;
                u=(double)q->packet->uv[0]+s*((double)q->packet->uv[6]-(double)q->packet->uv[0]);
                v=(double)q->packet->uv[1]+t*((double)q->packet->uv[3]-(double)q->packet->uv[1]);
                hm_sample(q->texture,u,v,texel);
                at=(py*(size_t)width+px)*4u;
                hm_blend(staged+at,texel,q->packet->rgba,q->source_factor,q->destination_factor);
                ++local_samples;
            }
        }
        if(local_samples!=0u){++covered;samples+=local_samples;}
    }
    for(i=0u;i<(size_t)height;++i)
        memcpy(out_pixels+i*stride_bytes,staged+i*row_bytes,row_bytes);
    out_stats->packets_with_coverage=covered; out_stats->pixel_samples=samples;
cleanup:
    free(staged); free(prepared); return status;
}
