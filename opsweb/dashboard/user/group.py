# coding:utf8
from django.views.generic import TemplateView, View, ListView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group, User, Permission, ContentType
from django.http import JsonResponse, HttpResponse, QueryDict, Http404
from django.core import serializers
from django.shortcuts import render
from django.conf import settings

import logging

logger = logging.getLogger('opsweb')


# 所有组列表
class GroupListView(ListView):
    model = Group
    template_name = 'user/grouplist.html'

    def post(self, request):
        if not request.user.has_perm("auth.add_group"):
            return HttpResponse('Forbidden')
        ret = {'status': 0}
        name = request.POST.get('name', '')
        if name:
            try:
                group = Group()
                group.name = name
                group.save()
            except Exception as e:
                ret['status'] = 1
                ret['ermsg'] = e.args

        return JsonResponse(ret, safe=True)


# 获取用户组信息
class GroupView(View):
    @method_decorator(login_required)
    @method_decorator(permission_required("auth.list_group", login_url=settings.PERMISSION_NONE_URL))
    def get(self, request):
        uid = request.GET.get('uid', '')
        ret = {'status': 0}
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist as e:
            ret['status'] = 1
            ret['errmsg'] = '用户不存在{}'.format(e.args)
        all_groups = Group.objects.all()
        groups = [group for group in all_groups if group not in user.groups.all()]
        return HttpResponse(serializers.serialize("json", groups), content_type="application/json")


# 将用户添加到指定组((用户列表中 添加到组 显示下拉框内容))
class UserGroupView(View):
    ''' 
        显示组下所有的用户列表 
    '''

    @method_decorator(login_required)
    @method_decorator(permission_required("auth.list_group", login_url=settings.PERMISSION_NONE_URL))
    def get(self, request):
        gid = request.GET.get('gid', None)
        try:
            groups = Group.objects.get(pk=gid)
        except Exception as e:
            logging.error('{}'.format(e.args))
            return JsonResponse([], safe=False)
        users = groups.user_set.all()
        user_list = [{'id': user.id, 'username': user.username, 'email': user.email, 'name': user.profile.chinaname} for
                     user in users]
        return JsonResponse(user_list, safe=False)

    """
        将用户添加到指定组
    """

    def post(self, request):
        if not request.user.has_perm('auth.add_group'):
            return HttpResponse('Forbidden')
        ret = {"status": 0}
        uid = request.POST.get('uid', None)
        gid = request.POST.get('gid', None)

        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:

            logger.error("将用户添加至指定用户组，用户不存在，用户id为：{}".format(uid))
            ret['status'] = 1
            ret['errmsg'] = "用户不存在"
            return JsonResponse(ret, safe=True)

        try:
            group = Group.objects.get(pk=gid)
        except Group.DoesNotExist:

            logger.error("将用户添加至指定用户组，用户组不存在，用户组id为：{}".format(uid))
            ret['status'] = 1
            ret['errmsg'] = "用户组不存在"
            return JsonResponse(ret, safe=True)

        user.groups.add(group)
        return JsonResponse(ret, safe=True)

    '''
        将用户从组中删除
    '''

    def delete(self, request):
        if not request.user.has_perm('auth.delete_group'):
            return HttpResponse('Forbidden')
        ret = {"status": 0}
        data = QueryDict(request.body)
        uid = data.get('userid', None)
        gid = data.get('groupid', None)
        try:
            user = User.objects.get(pk=uid)
            group = Group.objects.get(pk=gid)
            group.user_set.remove(user)
        except User.DoesNotExist:
            ret['status'] = 1
            ret['errmsg'] = "用户不存在"
        except Group.DoesNotExist:
            ret['status'] = 1
            ret['errmsg'] = "用户组不存在"
        except Exception as e:
            ret['status'] = 1
            ret['errmsg'] = e.args
        return JsonResponse(ret, safe=True)


# 组权限管理列表视图
class GroupPermissionListViwe(TemplateView):
    template_name = 'user/group_permission_list.html'

    def get_context_data(self, **kwargs):
        context = super(GroupPermissionListViwe, self).get_context_data(**kwargs)
        context['group_permission'] = self.get_group_permission()  # 取出现有权限 在模板中匹配 有权限则选中
        context['content_type'] = ContentType.objects.all()  # 取出所有权限
        context['group'] = self.request.GET.get('gid', '')  # 传入组id 提交时获取

        return context

    def get_group_permission(self):
        gid = self.request.GET.get('gid', '')
        try:
            gruop = Group.objects.get(pk=gid)
            # 返回现有权限
            return [per.id for per in gruop.permissions.all()]
        except Group.DoesNotExist as e:
            logger.error('组不存在{0}'.format(e.args))
            return Http404

    @method_decorator(login_required)
    @method_decorator(permission_required("auth.list_group", login_url=settings.PERMISSION_NONE_URL))
    def get(self, request, *args, **kwargs):
        return super(GroupPermissionListViwe, self).get(request, *args, **kwargs)


    def post(self, request):
        if not request.user.has_perm("auth.change_group"):
            return HttpResponse('Forbidden')
        permission_id_list = request.POST.getlist('permission', [])
        groupid = request.POST.get('group', '')
        ret = {"status": 0, "next_url": "/group/list/"}
        try:
            group = Group.objects.get(pk=groupid)  # 取出组
        except Group.DoesNotExist as e:
            logger.error("用户组不存在{}".format(e.args))
            ret['status'] = 1
            ret['errmsg'] = '用户组不存在'
        else:
            if permission_id_list:
                # 取出权限
                permissions_obj = Permission.objects.filter(id__in=permission_id_list)
                # 给组赋予权限
                group.permissions = permissions_obj
        return render(request, settings.TEMPLATE_JUMP, ret)


# 查看单个组的权限
# list view方法
'''

class GroupPermissionView(ListView):
    template_name = "user/group_permission.html"
    model = Permission
    context_object_name = 'object_list'

    """ 
        重载父类方法，父类方法中默认返回models所有数据
        if self.queryset is not None:
            queryset = self.queryset
            if isinstance(queryset, QuerySet):
                queryset = queryset.all()
        elif self.model is not None:
            queryset = self.model._default_manager.all()
            
        传入返回数据（通过某一条object）
    """
    def get_queryset(self):
        queryset = super(GroupPermissionView, self).get_queryset()
        gid = self.request.GET.get("gid", 0)
        try:
            group = Group.objects.get(pk=gid)
            permission = group.permissions.all()
        except Group.DoesNotExist as e:
            logger.error("所查id为 {0} 用户组不存在，{1}".format(gid, e.args))
            raise Http404
        queryset = queryset.filter(id__in=[p.id for p in permission])
        return queryset
'''


# 查看单个组的权限
# 使用template view方法
class GroupPermissionView(TemplateView):
    template_name = "user/group_permission.html"

    def get_context_data(self, **kwargs):
        context_data = super(GroupPermissionView, self).get_context_data(**kwargs)
        gid = self.request.GET.get("gid", 0)
        try:
            group = Group.objects.get(pk=gid)
            context_data["permissions"] = group.permissions.all()
            context_data["gid"] = gid
        except Group.DoesNotExist as e:
            logger.error("所查id为 {0} 用户组不存在，{1}".format(gid, e.args))
            raise Http404
        return context_data

    @method_decorator(login_required)
    @method_decorator(permission_required("auth.list_group", login_url=settings.PERMISSION_NONE_URL))
    def get(self, request, *args, **kwargs):
        return super(GroupPermissionView, self).get(request, *args, **kwargs)

    # 删除组中的某个权限\
    """ 
    def post(self, request):
        permission_id = request.POST.get('permissionid', 0)
        g_id = request.POST.get('gid', 0)
        print g_id
        pass

    """
